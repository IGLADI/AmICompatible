# AmICompatible

## Prerequisites

-   [Python 3.x](https://www.python.org/downloads/)
-   [Terraform](https://www.terraform.io/downloads.html)
-   [Azure Subscription](https://azure.microsoft.com/en-us/pricing/purchase-options/azure-account?icid=azurefreeaccount)

## Setup

### Local Development

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create Azure Service Principal:

```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

az login

az ad sp create-for-rbac --name "AIC" --role contributor --scopes /subscriptions/<subscription_id>
```

3. Configure credentials:

    - Copy `aic.conf.example` to `aic.conf`
        ```bash
        cp aic.conf.example aic.conf
        ```
    - Update the following values in `aic.conf`:
        - subscription_id: Your Azure subscription ID
        - tenant_id: From service principal output
        - appId: From service principal output
        - client_secret: From service principal output (password)

4. Run the application:

```bash
python main.py
```
