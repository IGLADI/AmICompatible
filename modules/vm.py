from . import terraform, ssh
import subprocess
import os
import shutil
import time
import shlex


def deploy_and_test_vm(terraform_dir, os_name, cfg):
    print(f"Deploying {os_name} VM")
    terraform.init_and_apply(terraform_dir, os_name)

    try:
        print("Getting the public IP address...")
        ip = terraform.get_public_ip(terraform_dir)

        print("Connecting to the VM via SSH...")
        client = ssh.connect_to_vm(ip)

        print("Creating Ansible inventory...")
        create_ansible_inventory(ip)

        print("Downloading remote dependencies...")
        download_remote_dependency()

        print("Copying project files...")
        copy_project_files(ip, cfg["project_root"])

        print("Running Jenkins pipeline...")
        run_jenkins_pipeline(client, cfg["jenkins_file"], cfg["plugin_file"], cfg["project_root"])
    finally:
        print("Cleaning up...")
        client.close()
        terraform.destroy(terraform_dir)


def create_ansible_inventory(ip):
    inventory = f"{ip} ansible_user=aic ansible_ssh_private_key_file=./temp/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no'"
    with open("./temp/inventory.ini", "w") as ini:
        ini.write(inventory)


def download_remote_dependency():
    subprocess.run("ansible-playbook -i ./temp/inventory.ini ansible/dependency.yml", shell=True, check=True)


def copy_project_files(ip, project_root):
    project_path = os.path.abspath(project_root)
    subprocess.run(f"scp -i ./temp/id_rsa -r {project_path} aic@{ip}:~/project", shell=True, check=True)
    subprocess.run(f"scp -i ./temp/id_rsa ./modules/approve-scripts.groovy aic@{ip}:~", shell=True, check=True)


def run_jenkins_pipeline(client, jenkins_file, plugin_file, project_root):
    print("Getting Jenkins initial admin password...")
    stdout, stderr = ssh.execute_ssh_command(client, "sudo cat /var/lib/jenkins/secrets/initialAdminPassword", print_output=False)
    admin_password = stdout.strip()

    # Install Jenkins plugins
    if os.path.exists(os.path.join(project_root, plugin_file)):
        print("Installing Jenkins plugins...")
        with open(os.path.join(project_root, plugin_file), "r") as file:
            plugins = [line.strip() for line in file if line.strip()]

        if plugins:
            plugins_str = " ".join(plugins)
            ssh.execute_ssh_command(
                client, f"java -jar jenkins-cli.jar -auth admin:{admin_password} -s http://localhost:8080 install-plugin {plugins_str} -deploy"
            )
            # Restart Jenkins to apply plugin changes
            ssh.execute_ssh_command(client, "sudo systemctl restart jenkins")
            # Wait for Jenkins to come back up
            time.sleep(30)

    print("Creating Jenkins job...")
    with open(os.path.join(project_root, jenkins_file), "r") as file:
        jenkins_file_content = file.read()

    # This xml is based from a pipline made trough the Jenkins UI (exported by adding /config.xml to the job URL)
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
    job_config = shlex.quote(job_config)

    ssh.execute_ssh_command(client, f"echo {job_config} > job_config.xml")

    # Create and trigger the job
    # See https://www.jenkins.io/doc/book/managing/cli/
    ssh.execute_ssh_command(
        client,
        f"java -jar jenkins-cli.jar -auth admin:{admin_password} -s http://localhost:8080 create-job test_job < ~/job_config.xml",
    )
    print("Approving Jenkins job...")
    ssh.execute_ssh_command(
        client, f"java -jar jenkins-cli.jar -auth admin:{admin_password} -s http://localhost:8080  groovy = < approve-scripts.groovy"
    )
    print("Triggering Jenkins job...")
    ssh.execute_ssh_command(
        client, f"cd project && java -jar ~/jenkins-cli.jar -auth admin:{admin_password} -s http://localhost:8080 build test_job -f -v"
    )


def cleanup():
    if os.path.exists("temp"):
        shutil.rmtree("temp")
