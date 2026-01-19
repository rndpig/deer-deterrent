# Setting Static IP on Dell Server

## Quick Reference
Current IP: `192.168.7.215`
Gateway: Likely `192.168.7.1` (eero router)
DNS: `192.168.7.1` or `8.8.8.8`

## Steps to Configure Static IP on Ubuntu

### 1. Check Current Network Configuration
```bash
# SSH into server
ssh rndpig@192.168.7.215

# Check current network interface name
ip addr show

# Check current gateway
ip route show

# Check DNS servers
resolvectl status
```

### 2. Edit Netplan Configuration
Ubuntu uses Netplan for network configuration:

```bash
# Find netplan config file
sudo ls /etc/netplan/

# Edit the config file (usually 00-installer-config.yaml or 01-network-manager-all.yaml)
sudo nano /etc/netplan/01-netcfg.yaml
```

### 3. Configure Static IP
Replace the DHCP configuration with static settings:

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    <interface-name>:  # Replace with your interface (e.g., eth0, enp0s3, ens18)
      dhcp4: no
      addresses:
        - 192.168.7.215/24
      routes:
        - to: default
          via: 192.168.7.1  # Your eero router IP
      nameservers:
        addresses:
          - 192.168.7.1     # eero router
          - 8.8.8.8         # Google DNS (backup)
```

### 4. Apply Configuration
```bash
# Test the configuration (won't apply changes)
sudo netplan try

# If it looks good, press Enter to accept
# Or apply directly
sudo netplan apply

# Verify the changes
ip addr show
```

### 5. Reboot to Confirm
```bash
sudo reboot
```

After reboot, verify you can still SSH using:
```bash
ssh rndpig@192.168.7.215
```

## Important Notes
- **Write down the settings** before making changes in case you need to revert
- Keep the SSH session open while testing to avoid getting locked out
- The interface name varies (eth0, enp0s3, ens18, etc.) - use `ip addr` to find yours
- Make sure 192.168.7.215 isn't in the DHCP pool range (usually safe above .200)

## Recommendation
**Use DHCP Reservation on eero instead** - it's easier and safer. Only use static IP on server if you can't access eero settings.
