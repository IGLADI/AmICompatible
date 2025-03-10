# this file has been based on an export made with https://github.com/Azure/aztfexport

terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}


provider "azurerm" {
  features {}

  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
  client_id       = var.appId
  client_secret   = var.client_secret
}

resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.region
}

resource "azurerm_windows_virtual_machine" "main" {
  admin_password = var.password
  admin_username = "aic"
  location       = var.region
  name           = "aic-vm"
  network_interface_ids = [
    azurerm_network_interface.main.id,
  ]
  resource_group_name = azurerm_resource_group.main.name
  size                = var.vm_size
  additional_capabilities {
  }

  boot_diagnostics {
  }

  # windows client images do not support AutomaticByPlatform, some windows server versions require it
  patch_mode = var.os == "Windows11" ? "AutomaticByOS" : "AutomaticByPlatform"

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
  }

  source_image_reference {
    # see https://learn.microsoft.com/en-us/azure/virtual-machines/linux/cli-ps-findimage#code-try-6
    publisher = lookup({
      WindowsServer-2025-datacenter = "MicrosoftWindowsServer"
      WindowsServer-2022-datacenter = "MicrosoftWindowsServer"
      # we do not support Windows Server 2019 as the ssh extension does not work with it
      WindowsServer-2016-datacenter = "MicrosoftWindowsServer"
      Windows11                     = "microsoftwindowsdesktop"
      # same as above, we do not support Windows 10 as the ssh extension does not work with it
    }, var.os)
    offer = lookup({
      WindowsServer-2025-datacenter = "WindowsServer"
      WindowsServer-2022-datacenter = "WindowsServer"
      WindowsServer-2016-datacenter = "WindowsServer"
      Windows11                     = "windows-11"
    }, var.os)
    sku = lookup({
      WindowsServer-2025-datacenter = "2025-datacenter-azure-edition"
      WindowsServer-2022-datacenter = "2022-datacenter-azure-edition"
      WindowsServer-2016-datacenter = "2016-datacenter"
      Windows11                     = "win11-22h2-entn"
    }, var.os)
    version = "latest"
  }
  depends_on = [
    azurerm_network_interface.main,
  ]
}

resource "azurerm_virtual_machine_extension" "main" {
  auto_upgrade_minor_version = true
  name                       = "WindowsOpenSSH"
  publisher                  = "Microsoft.Azure.OpenSSH"
  settings                   = jsonencode({})
  type                       = "WindowsOpenSSH"
  type_handler_version       = "3.0"
  virtual_machine_id         = azurerm_windows_virtual_machine.main.id
  depends_on = [
    azurerm_windows_virtual_machine.main,
  ]
}

resource "azurerm_network_interface" "main" {
  location            = var.region
  name                = "win556_z3"
  resource_group_name = azurerm_resource_group.main.name
  ip_configuration {
    name                          = "ipconfig1"
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.main.id
    subnet_id                     = azurerm_subnet.main.id
  }
  depends_on = [
    azurerm_public_ip.main,
    azurerm_subnet.main,
  ]
}

resource "azurerm_network_interface_security_group_association" "main" {
  network_interface_id      = azurerm_network_interface.main.id
  network_security_group_id = azurerm_network_security_group.main.id
  depends_on = [
    azurerm_network_interface.main,
    azurerm_network_security_group.main,
  ]
}

resource "azurerm_network_security_group" "main" {
  location            = var.region
  name                = "win-nsg"
  resource_group_name = azurerm_resource_group.main.name
  depends_on = [
    azurerm_resource_group.main,
  ]
}

resource "azurerm_network_security_rule" "main" {
  access                      = "Allow"
  destination_address_prefix  = "*"
  destination_port_range      = "22"
  direction                   = "Inbound"
  name                        = "SSH"
  network_security_group_name = "win-nsg"
  priority                    = 320
  protocol                    = "Tcp"
  resource_group_name         = azurerm_resource_group.main.name
  source_address_prefix       = "*"
  source_port_range           = "*"
  depends_on = [
    azurerm_network_security_group.main,
  ]
}

resource "azurerm_public_ip" "main" {
  allocation_method   = "Static"
  location            = var.region
  name                = "win-ip"
  resource_group_name = azurerm_resource_group.main.name
  depends_on = [
    azurerm_resource_group.main,
  ]
}

resource "azurerm_virtual_network" "main" {
  address_space       = ["10.0.0.0/16"]
  location            = var.region
  name                = "win-vnet"
  resource_group_name = azurerm_resource_group.main.name
  depends_on = [
    azurerm_resource_group.main,
  ]
}

resource "azurerm_subnet" "main" {
  address_prefixes     = ["10.0.0.0/24"]
  name                 = "default"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = "win-vnet"
  depends_on = [
    azurerm_virtual_network.main,
  ]
}

output "public_ip" {
  value = azurerm_public_ip.main.ip_address
}
