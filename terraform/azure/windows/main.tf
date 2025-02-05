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
  location = var.region
  name     = "aic-vm-rg"
}

# this is to prevent azure to auto create a separate NetworkWatcherRG which would not be known (and deleted) by terraform
# somimes azure still creates a NetworkWatcherRG, but empty which is fine
resource "azurerm_network_watcher" "main" {
  name                = "aic-vm-rg-nw"
  location            = var.region
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_windows_virtual_machine" "main" {
  admin_password      = var.password
  admin_username      = "aic"
  hotpatching_enabled = true
  location            = var.region
  name                = "win"
  network_interface_ids = [
    azurerm_network_interface.main.id,
  ]
  patch_mode          = "AutomaticByPlatform"
  reboot_setting      = "IfRequired"
  resource_group_name = "aic-vm-rg"
  secure_boot_enabled = true
  size                = var.vm_size
  vtpm_enabled        = true
  additional_capabilities {
  }

  boot_diagnostics {
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
  }

  source_image_reference {
    publisher = lookup({
      MicrosoftWindowsServer-2022-datacenter = "MicrosoftWindowsServer"
    }, var.os)
    offer = lookup({
      MicrosoftWindowsServer-2022-datacenter = "WindowsServer"
    }, var.os)
    sku = lookup({
      MicrosoftWindowsServer-2022-datacenter = "2022-datacenter-azure-edition-hotpatch"
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
  resource_group_name = "aic-vm-rg"
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
  resource_group_name = "aic-vm-rg"
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
  resource_group_name         = "aic-vm-rg"
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
  resource_group_name = "aic-vm-rg"
  depends_on = [
    azurerm_resource_group.main,
  ]
}

resource "azurerm_virtual_network" "main" {
  address_space       = ["10.0.0.0/16"]
  location            = var.region
  name                = "win-vnet"
  resource_group_name = "aic-vm-rg"
  depends_on = [
    azurerm_resource_group.main,
  ]
}

resource "azurerm_subnet" "main" {
  address_prefixes     = ["10.0.0.0/24"]
  name                 = "default"
  resource_group_name  = "aic-vm-rg"
  virtual_network_name = "win-vnet"
  depends_on = [
    azurerm_virtual_network.main,
  ]
}

output "public_ip" {
  value = azurerm_public_ip.main.ip_address
}
