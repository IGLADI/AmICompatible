<!-- Disclaimer: This README has been made w help of AI as well as a lot of documentation in the code -->

# AmICompatible

## Overview

AmICompatible (AIC) is a tool designed to help you test the compatibility of your software across different platforms. Whether you already have a [Jenkins](https://www.jenkins.io) pipeline in place or prefer to start with a simple [Jenkinsfile](https://www.jenkins.io/doc/pipeline/tour/hello-world/) that runs your script, AIC can help you quickly identify any compatibility issues with your software.

## Use Cases

-   **Script Compatibility Testing**: Quickly document which Linux distributions your script runs on by creating a Jenkinsfile that just executes the script.

    -   Example: Deploy an Nginx website => Run with AIC => Discover UFW is missing on some distros => Fix or document it.

-   **Software Retrocompatibility**: Test how well your software runs across different Windows versions.

-   **[Upcoming] Emulation Layer Testing**: Check how well your software performs with emulation layers like [Wine](https://www.winehq.org) or Proton for [Linux users.](https://www.protondb.com/explore)

-   **Quick Pipeline Execution**: Test a Jenkins pipeline without manually setting up a local Jenkins server.

## Prerequisites

-   [Python 3.x](https://www.python.org/downloads/)
-   [Terraform](https://www.terraform.io/downloads.html)
-   [Azure Subscription](https://azure.microsoft.com/en-us/pricing/purchase-options/azure-account?icid=azurefreeaccount)
-   [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
-   [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html)
-   Linux Host: We use Linux only tools like `ansible`, If you are on Windows, you can use [WSL](https://learn.microsoft.com/en-us/windows/wsl/install) or a Linux VM.

## Quick Start

1. **Clone Repository**

    ```bash
    git clone https://github.com/IGLADI/AmICompatible && cd AmICompatible
    ```

2. **Install dependencies**

    ```bash
    pip install -r requirements.txt
    ```

3. **Create Azure Service Principal**

    ```bash
    az login

    az ad sp create-for-rbac --name "AIC" --role contributor --scopes /subscriptions/<subscription_id>
    ```

4. **Edit the configuration file as needed**

    Copy `aic.yml.example` to `aic.yml`:

    ```bash
    cp aic.yml.example aic.yml
    ```

    Update `aic.yml`:

    ```bash
    nano aic.yml
    ```

5. **Run AIC**

    This would typically be done using GitHub Actions or similar (which would also handle the secrets in `aic.yml`).

    ```bash
    python main.py
    ```

## Limitation

AIC will install dependencies which might not come with the system. If your code uses these dependencies, it might work on AIC but not on a clean system. For example, Java will be installed by AIC but not present on a clean system.

AIC handles interruptions as much as possible; however, Terraform can be very sensitive to them, so interruptions are still seriously discouraged and you should always check for any cloud resources left when doing so to avoid any unnecessary costs.

## How to Add Providers

To add support for additional cloud providers or on-premises infrastructure, follow these steps:

### Method 1: Create a New Terraform Directory

1. **Create a new Terraform directory for the provider**

    ```bash
    mkdir terraform/aws
    ```

2. **Add Terraform configuration files**

    Add the necessary Terraform configuration files in the newly created directory to define the infrastructure for the provider.

3. **Modify the `main.py` script**

    ```bash
    nano main.py
    ```

    Example:

    ```python
    match cfg["platform"]:
        case "azure":
            terraform_dir = "./terraform/azure"
        case "aws":
            terraform_dir = "./terraform/aws"
        case _:
            print(f"Error: Unsupported platform '{cfg['platform']}' specified.")
            sys.exit(1)
    ```

    You may also need to update `config.py` to include any provider-specific variables.

    ```bash
    nano ./modules/config.py
    ```

4. **Update the configuration file**

    Ensure that the configuration file (`aic.yml`) includes the new provider and any required variables.

### Method 2: Edit Existing Terraform File with Environment Variables

1. **Move the existing Terraform files**

    ```bash
    mv terraform/azure/* terraform/
    ```

2. **Edit the Terraform files**

    Update the Terraform files to use environment variables for provider-specific configurations.

3. **Modify the `main.py` script**

    Update the `config.py` script to set the appropriate environment variables based on the provider specified in the configuration.

    ```bash
    nano ./modules/config.py
    ```

    Update the `main.py` script to work with one terraform directory.

    ```python
    terraform_dir = "./terraform"
    ```

4. **Update the configuration file**

    Ensure that the configuration file (`aic.yml`) includes the new provider and any required variables.

## How to Add Supported OS

To add support for additional operating systems, follow these steps:

1. **Update Terraform Main Configuration**

    Add the new OS to the `source_image_reference` lookup in the `main.tf` file for both Windows or Linux configurations.

    ```terraform
    source_image_reference {
      publisher = lookup({
        LinuxUbuntuServer_24_04-LTS = "Canonical",
        LinuxRhel9                  = "RedHat",
        LinuxDebian12               = "Debian",
        <new_os>                    = "<new_publisher>"
      }, var.os)
      offer = lookup({
        LinuxUbuntuServer_24_04-LTS = "ubuntu-24_04-lts",
        LinuxRhel9                  = "RHEL",
        LinuxDebian12               = "debian-12",
        <new_os>                    = "<new_offer>"
      }, var.os)
      sku = lookup({
        LinuxUbuntuServer_24_04-LTS = "server",
        LinuxRhel9                  = "90-gen2",
        LinuxDebian12               = "12-gen2",
        <new_os>                    = "<new_sku>"
      }, var.os)
      version = "latest"
    }
    ```

2. **Update Configuration File**

    Add the new OS to the `aic.yml` and `aic.yml.example` files.

    ```yaml
    os:
        # - UbuntuServer_24_04-LTS
        # - Debian12
        # - RHEL9
        # - <new_os>
    ```

3. **Add OS-Specific Code**

    If the new OS requires any specific setup or dependencies, update the corresponding code, this will likely be in the `ansible/linux/dependency.yml`

## Contributing

To contribute your changes (like adding support for a new provider), follow these steps:

Fork the repository and clone it to your local machine.

Create a new feature branch.

```bash
git checkout -b feature/add-aws-support
```

Code your changes and commit them.

```bash
git add .
git commit -m "Add AWS support"
```

Push to your fork.

```bash
git push origin feature/add-aws-support
```

> ℹ️ Ensure you document your changes and update the README if necessary.

Open a PR on the main repository to merge your changes.

Thank you for contributing to the open-source community!

## Troubleshooting

### VM Image Issues

If you encounter any issue while terraform deploys a specific VM image:

-   Check if your subscription tier is eligible for that image (a lot of images are not available for free plans).
-   Accept TOS when needed:

    ```bash
    az vm image terms accept --publisher resf --offer rockylinux-x86_64 --plan 9-base
    az vm image terms accept --publisher ntegralinc1586961136942 --offer ntg_fedora_41 --plan ntg_fedora_41
    ```

> ℹ️ We try to keep all TOS commands needed here, if you encounter one not listed here please contribute or open an issue.

### Terraform Apply Issues

If you encounter any issues with terraform, this is most likely due to a mismatch between the tfstate file and the actual resources in the cloud. To fix this, you can delete the tfstate file **and** delete any resources that were created by the script manually.

```bash
rm ./terraform/azure/linux/*.tfstate* > /dev/null 2>&1
rm ./terraform/azure/windows/*.tfstate* > /dev/null 2>&1
```

> ℹ️ You will need to wait for the resources to be deleted before running the script again.

### Azure Limitations

If you encounter an Azure limitation, for example `PublicIPCountLimitReached` try decreasing `max_threads` in `aic.yml` or increase your subscription limits if you are on a paid plan.

### Windows SSH Extension Issues

The extension has a timeout of ~3 minutes to setup ssh, if you encounter any issues with the extension, try increasing `vm_size` in `aic.yml`.

### OSError: Too many open files

If you encounter the error `OSError: [Errno 24] Too many open files`, try decreasing `max_threads` in `aic.yml`.
