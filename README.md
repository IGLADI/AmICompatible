<!-- Disclaimer: This README has been made w help of AI -->

# AmICompatible

## Overview

AmICompatible (AIC) is a tool designed to help you test the compatibility of your software across different platforms. Whether you already have a Jenkins pipeline in place or prefer to start with a simple Jenkinsfile that runs your script, AIC can help you quickly identify any compatibility issues with your software.

## Use Cases

-   **Script Compatibility Testing**: Quickly document which Linux distributions your script runs on by creating a Jenkinsfile that just executes the script.

    -   Example: Deploy an Nginx website => Run with AIC => Discover UFW is missing on some distros => Fix or document it.

-   **Software Retrocompatibility**: Test how well your software runs across different Windows versions.

-   **[Upcoming] Emulation Layer Testing**: Check how well your software performs with emulation layers like [Wine](https://www.winehq.org) or Proton for [Linux users.](https://www.protondb.com/explore)

## Prerequisites

-   [Python 3.x](https://www.python.org/downloads/)
-   [Terraform](https://www.terraform.io/downloads.html)
-   [Azure Subscription](https://azure.microsoft.com/en-us/pricing/purchase-options/azure-account?icid=azurefreeaccount)
-   [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
-   [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html)

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

**Note:** Ensure you document your changes and update the README if necessary.

Open a PR on the main repository to merge your changes.

Thank you for contributing to the open-source community!
