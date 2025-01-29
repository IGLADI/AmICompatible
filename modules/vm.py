from . import terraform, ssh


def deploy_and_test_vm(terraform_dir, os_name):
    print(f"Deploying {os_name} VM")
    terraform.init_and_apply(terraform_dir, os_name)

    print("Getting the public IP address...")
    ip = terraform.get_public_ip(terraform_dir)

    print("Connecting to the VM via SSH...")
    client = ssh.connect_to_vm(ip)
    # run a simple command to test the connection
    stdin, stdout, stderr = client.exec_command("hostname")
    print(f"VM hostname: {stdout.read().decode()}")

    print("Closing SSH connection...")
    client.close()

    # cleanup cloud resources
    terraform.destroy(terraform_dir)
