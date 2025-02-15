import os
import secrets
import shlex
import shutil
import subprocess
import time

from . import ssh, terraform


def deploy_and_test_vm(terraform_dir, os_name, cfg, password=None, windows=False):
    print(f"Deploying {os_name} VM")
    terraform.init_and_apply(terraform_dir, os_name)

    try:
        print("Getting the public IP address...")
        ip = terraform.get_public_ip(terraform_dir)

        print("Connecting to the VM via SSH...")
        # for windows this only serves to wait for ssh to be available
        client = ssh.connect_to_vm(ip, password=password)

        print("Creating Ansible inventory...")
        create_ansible_inventory(ip, password, windows=windows)

        print("Downloading remote dependencies...")
        download_remote_dependency(password, windows, ip)

        if windows:
            print("Recreating the ssh connection with powershell as shell...")
            client.close()
            client = ssh.connect_to_vm(ip, password=password)

        print("Copying project files...")
        copy_project_files(client, ip, cfg["project_root"], password, windows)

        print("Running Jenkins pipeline...")
        run_jenkins_pipeline(client, cfg["jenkins_file"], cfg["plugin_file"], cfg["project_root"], password, windows)
    finally:
        print("Cleaning up...")
        terraform.destroy(terraform_dir)
        if client:
            client.close()


def create_ansible_inventory(ip, password=None, powershell=False, windows=False):
    if password and windows:
        if powershell:
            inventory = f"{ip} ansible_user=aic ansible_password={password} ansible_ssh_common_args='-o StrictHostKeyChecking=no' ansible_remote_tmp='C:\\Windows\\Temp' ansible_shell_type=powershell ansible_python_interpreter=none"
        else:
            # ansible ssh via cmd and then run powershell
            inventory = f"{ip} ansible_user=aic ansible_password={password} ansible_ssh_common_args='-o StrictHostKeyChecking=no' ansible_remote_tmp='C:\\Windows\\Temp' ansible_shell_type=cmd ansible_python_interpreter=none"
    elif not windows:
        inventory = f"{ip} ansible_user=aic ansible_ssh_private_key_file=./temp/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no'"
    else:
        raise ValueError("This combination of arguments is not supported")
    with open("./temp/inventory.ini", "w") as ini:
        ini.write(inventory)


def download_remote_dependency(password=None, windows=False, ip=None):
    if password and windows:
        # set pwsh as default shell
        subprocess.run(
            "ansible-playbook -i ./temp/inventory.ini ansible/windows/shell.yml",
            shell=True,
            check=True,
        )
        # install dependencies
        create_ansible_inventory(ip, password, powershell=True, windows=windows)
        subprocess.run(
            "ansible-playbook -i ./temp/inventory.ini ansible/windows/dependency.yml",
            shell=True,
            check=True,
        )
    elif not windows:
        # rsa path is in the ini file
        subprocess.run("ansible-playbook -i ./temp/inventory.ini ansible/linux/dependency.yml", shell=True, check=True)
    else:
        raise ValueError("This combination of arguments is not supported")


def copy_project_files(client, ip, project_root, password=None, windows=False):
    if password and windows:
        # scp does not support password auth OOTB so we use sshpass to automate the password input
        # for windows path check out https://stackoverflow.com/questions/10235778/scp-from-linux-to-windows
        ssh.execute_ssh_command(
            client,
            "New-Item -ItemType Directory -Path C:\\Windows\\system32\\config\\systemprofile\\AppData\\Local\\Jenkins\\.jenkins\\workspace\\test_job",
        )
        subprocess.run(
            f"sshpass -p {password} scp -r {project_root}/* aic@{ip}:C:/Windows/system32/config/systemprofile/AppData/Local/Jenkins/.jenkins/workspace/test_job",
            shell=True,
            check=True,
        )
        subprocess.run(f"sshpass -p {password} scp ./modules/approve-scripts.groovy aic@{ip}:/C:/Users/aic", shell=True, check=True)
    elif not windows:
        # create the default folder jenkins would use so we can place the project files there (else the user would have to edit his Jenkinsfile w the workspace path)
        ssh.execute_ssh_command(client, "sudo mkdir -p /var/lib/jenkins/workspace/test_job")
        # copy the project files to the VM
        subprocess.run(f"scp -i ./temp/id_rsa -r {project_root} aic@{ip}:~/project", shell=True, check=True)
        ssh.execute_ssh_command(client, "sudo cp ~/project/* /var/lib/jenkins/workspace/test_job")
        # regive jenkins ownership of the workspace
        ssh.execute_ssh_command(client, "sudo chown -R jenkins:jenkins /var/lib/jenkins")
        subprocess.run(f"scp -i ./temp/id_rsa ./modules/approve-scripts.groovy aic@{ip}:~", shell=True, check=True)
    else:
        raise ValueError("This combination of arguments is not supported")


def run_jenkins_pipeline(client, jenkins_file, plugin_file, project_root, password=None, windows=False):
    print("Getting Jenkins initial admin password...")
    # stderr has to be there even if we don't use it else stdout will contain a tuple
    if windows:
        # some windows version will store this in a different path or even multiple times, command to find the file and then get the content w help of chatGPT
        stdout, stderr = ssh.execute_ssh_command(
            client,
            'Get-Content -Path (Get-ChildItem -Path "C:\\" -Recurse -Filter "initialAdminPassword" -ErrorAction SilentlyContinue -Force -File -OutVariable files | Select-Object -First 1 -ExpandProperty FullName)',
            print_output=False,
        )
    else:
        stdout, stderr = ssh.execute_ssh_command(client, "sudo cat /var/lib/jenkins/secrets/initialAdminPassword", print_output=False)

    jenkins_password = stdout.strip()

    install_jenkins_plugins(client, jenkins_password, plugin_file, project_root, windows)

    print("Creating Jenkins job...")
    with open(os.path.join(project_root, jenkins_file), "r") as file:
        jenkins_file_content = file.read()

    # This xml is based from a pipline made trough the Jenkins UI (exported by adding /config.xml to the job URL)
    # could also be done in a separate file and then we wouldn't need to escape it as we would scp it but that's more difficult to replace the jenkins_file_content
    job_config = f"""<flow-definition plugin="workflow-job@1498.v33a_0c6f3a_4b_4">
<description/>
<keepDependencies>false</keepDependencies>
<properties/>
<definition class="org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition" plugin="workflow-cps@4014.vcd7dc51d8b_30">
<script>{jenkins_file_content}</script>
<sandbox>false</sandbox>
</definition>
<triggers/>
<disabled>false</disabled>
</flow-definition>"""

    # Escape the job config for the shell
    if windows:
        # pwsh escape done w help of chatGPT
        ssh.execute_ssh_command(client, f"@'\n{job_config}\n'@ | Out-File -Encoding UTF8 job_config.xml")
    else:
        job_config = shlex.quote(job_config)
        ssh.execute_ssh_command(client, f"echo {job_config} > job_config.xml")

    # Create and trigger the job
    # See https://www.jenkins.io/doc/book/managing/cli/
    if windows:
        ssh.execute_ssh_command(
            client,
            f"Get-Content C:\\Users\\aic\\job_config.xml | java -jar jenkins-cli.jar -auth admin:{jenkins_password} -s http://localhost:8080 create-job test_job",
        )
    else:
        ssh.execute_ssh_command(
            client,
            # we could also pipe with a cat to make it more like the pwsh command but that's one more dependency and it's less good practice
            f"java -jar jenkins-cli.jar -auth admin:{jenkins_password} -s http://localhost:8080 create-job test_job < ~/job_config.xml",
        )
    # we need to approve the job as it's not sandboxed, see groovy script for source
    print("Approving Jenkins job...")
    if windows:
        ssh.execute_ssh_command(
            client,
            f"Get-Content C:\\Users\\aic\\approve-scripts.groovy | java -jar jenkins-cli.jar -auth admin:{jenkins_password} -s http://localhost:8080  groovy =",
        )
    else:
        ssh.execute_ssh_command(
            client, f"java -jar jenkins-cli.jar -auth admin:{jenkins_password} -s http://localhost:8080  groovy = < approve-scripts.groovy"
        )
    print("Triggering Jenkins job...")
    if windows:
        ssh.execute_ssh_command(
            client,
            f"java -jar jenkins-cli.jar -auth admin:{jenkins_password} -s http://localhost:8080 build test_job -f -v",
        )
    else:
        ssh.execute_ssh_command(
            client,
            f"cd /var/lib/jenkins/workspace/test_job && java -jar ~/jenkins-cli.jar -auth admin:{jenkins_password} -s http://localhost:8080 build test_job -f -v",
        )


def install_jenkins_plugins(client, jenkins_password, plugin_file, project_root, windows):
    if os.path.exists(os.path.join(project_root, plugin_file)):
        print("Installing Jenkins plugins...")
        with open(os.path.join(project_root, plugin_file), "r") as file:
            plugins = [line.strip() for line in file if line.strip()]

        if plugins:
            plugins_str = " ".join(plugins)
            ssh.execute_ssh_command(
                client, f"java -jar jenkins-cli.jar -auth admin:{jenkins_password} -s http://localhost:8080 install-plugin {plugins_str} -deploy"
            )
            # Restart Jenkins to apply plugin changes
            if windows:
                ssh.execute_ssh_command(client, "Restart-Service Jenkins")
            else:
                ssh.execute_ssh_command(client, "sudo systemctl restart jenkins")
            # Wait for Jenkins to come back up
            time.sleep(30)
    else:
        print("No Jenkins plugins file found. Skipping plugin installation.")


def cleanup():
    if os.path.exists("temp"):
        shutil.rmtree("temp")


def generate_password():
    while True:
        password = secrets.token_urlsafe(32)
        # check if it fulfills the azure password requirements (made with help of copilot)
        if any(c.islower() for c in password) and any(c.isupper() for c in password) and any(c.isdigit() for c in password):
            return password
        else:
            print("Password does not meet Azure requirements, generating a new one...")
