# AmICompatible

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
    cp aic.yml.example aic.yaml
    ```

    Update `aic.yaml`:

    ```bash
    nano aic.yaml
    ```

5. **Run AIC**

    This would typically be done using github actions or similar (which would also handle the secrets in `aic.yml`).

    ```bash
    python main.py
    ```
