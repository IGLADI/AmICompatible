import os
import shlex
import time

import paramiko

from . import ssh


def run_jenkins_pipeline(client: paramiko.SSHClient, jenkins_file: str, plugin_file: str, project_root: str, windows: bool = False) -> None:
    """
    Run the Jenkins pipeline.

    Args:
        client: SSH client connected to the VM.
        jenkins_file: Path to the Jenkins file base on the project root.
        plugin_file: Path to the Jenkins plugin file.
        project_root: Root directory of the project.
        windows: Whether the VM is a Windows VM.
    """
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
            f"Get-Content C:\\Users\\aic\\job_config.xml | java -jar jenkins-cli.jar -auth admin:{jenkins_password} -s http://localhost:8080 create-job aic_job",
        )
    else:
        ssh.execute_ssh_command(
            client,
            # we could also pipe with a cat to make it more like the pwsh command but that's one more dependency and it's less good practice in unix
            f"java -jar jenkins-cli.jar -auth admin:{jenkins_password} -s http://localhost:8080 create-job aic_job < ~/job_config.xml",
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
    try:
        ssh.execute_ssh_command(
            client,
            f"java -jar jenkins-cli.jar -auth admin:{jenkins_password} -s http://localhost:8080 build aic_job -f -v",
        )
    except Exception as e:
        raise RuntimeError("Jenkins pipeline failed. This is not an AIC error. Check the logs for more information.") from e


def install_jenkins_plugins(client: paramiko.SSHClient, jenkins_password: str, plugin_file: str, project_root: str, windows: bool) -> None:
    """
    Install Jenkins plugins.

    Args:
        client: SSH client connected to the VM.
        jenkins_password: Jenkins admin password.
        plugin_file: Path to the Jenkins plugin file.
        project_root: Root directory of the project.
        windows: Whether the VM is a Windows VM.
    """
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
            wait_jenkins(client)
    else:
        print("No Jenkins plugins file found. Skipping plugin installation.")


def wait_jenkins(client: paramiko.SSHClient, wait_time: int = 10, max_retries: int = 5) -> None:
    """
    Wait for Jenkins to come back up.

    Args:
        client: SSH client connected to the VM.
        wait_time: Time to wait between retries.
        max_retries: Maximum number of retries.

    Raises:
        RuntimeError: If Jenkins does not come back up within the maximum retries.
    """
    print("Waiting for Jenkins to come back up...")
    for retry in range(1, max_retries + 1):
        try:
            ssh.execute_ssh_command(client, "java -jar jenkins-cli.jar -s http://localhost:8080 who-am-i", print_output=False)
            return
        except Exception:
            time.sleep(wait_time)
    raise RuntimeError("Max retries reached. Jenkins did not come back up.")
