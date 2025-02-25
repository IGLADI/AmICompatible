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

resource "azurerm_virtual_network" "main" {
  name                = "aic-vm-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_subnet" "main" {
  name                 = "aic-vm-subnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_public_ip" "main" {
  name                = "aic-vm-ip"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
}

resource "azurerm_network_interface" "main" {
  name                = "aic-vm-nic"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.main.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.main.id
  }
}

resource "azurerm_network_security_group" "main" {
  name                = "aic-vm-nsg"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  security_rule {
    name                       = "SSH"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_network_interface_security_group_association" "main" {
  network_interface_id      = azurerm_network_interface.main.id
  network_security_group_id = azurerm_network_security_group.main.id
}

resource "azurerm_linux_virtual_machine" "main" {
  name                = "aic-vm"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  # use a different vm size for arm as it is not supported by all sizes
  size                            = var.arm ? var.arm_vm_size : var.vm_size
  disable_password_authentication = true

  admin_username = "aic"

  admin_ssh_key {
    username   = "aic"
    public_key = file(var.ssh_public_key_path)
  }

  network_interface_ids = [
    azurerm_network_interface.main.id
  ]

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    # see https://learn.microsoft.com/en-us/azure/virtual-machines/linux/cli-ps-findimage#code-try-6
    publisher = lookup({
      LinuxUbuntuServer_24_04-LTS     = "Canonical"
      LinuxUbuntuServer_24_04-LTS-ARM = "Canonical"
      LinuxDebian12                   = "Debian"
      LinuxDebian12-ARM               = "Debian"
      LinuxRhel9                      = "RedHat"
      LinuxRhel9-ARM                  = "RedHat"
      LinuxFedora41                   = "ntegralinc1586961136942"
      LinuxRocky9                     = "resf"
      LinuxAlma9                      = "almalinux"
      LinuxOracle9                    = "oracle"
      LinuxSuse15                     = "suse"
      LinuxSuse15-ARM                 = "suse"
    }, var.os)
    offer = lookup({
      LinuxUbuntuServer_24_04-LTS     = "ubuntu-24_04-lts"
      LinuxUbuntuServer_24_04-LTS-ARM = "0001-com-ubuntu-server-jammy"
      LinuxDebian12                   = "debian-12"
      LinuxDebian12-ARM               = "debian-12"
      LinuxRhel9                      = "RHEL"
      LinuxRhel9-ARM                  = "rhel-arm64"
      LinuxFedora41                   = "ntg_fedora_41"
      LinuxRocky9                     = "rockylinux-x86_64"
      LinuxAlma9                      = "almalinux-x86_64"
      LinuxOracle9                    = "oracle-linux"
      LinuxSuse15                     = "sles-15-sp5-basic"
      LinuxSuse15-ARM                 = "sles-15-sp6-arm64"
    }, var.os)
    sku = lookup({
      LinuxUbuntuServer_24_04-LTS     = "server"
      LinuxUbuntuServer_24_04-LTS-ARM = "22_04-lts-arm64"
      LinuxDebian12                   = "12-gen2"
      LinuxDebian12-ARM               = "12-arm64"
      LinuxRhel9                      = "90-gen2"
      LinuxRhel9-ARM                  = "9_5-arm64"
      LinuxFedora41                   = "ntg_fedora_41"
      LinuxRocky9                     = "9-base"
      LinuxAlma9                      = "9-gen1"
      LinuxOracle9                    = "ol94-lvm"
      LinuxSuse15                     = "gen2"
      LinuxSuse15-ARM                 = "gen2"
    }, var.os)
    version = "latest"
  }

  # only some images need to specify a plan
  # w help of chatGPT for dynamic block
  dynamic "plan" {
    for_each = lookup({
      LinuxRocky9   = [{ name = "9-base", product = "rockylinux-x86_64", publisher = "resf" }]
      LinuxFedora41 = [{ name = "ntg_fedora_41", product = "ntg_fedora_41", publisher = "ntegralinc1586961136942" }]
    }, var.os, [])

    content {
      name      = plan.value.name
      product   = plan.value.product
      publisher = plan.value.publisher
    }
  }
}

output "public_ip" {
  value = azurerm_public_ip.main.*.ip_address
}
