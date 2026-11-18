#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 Arm VM on Oracle Cloud for the demo. Run on the server:
#   curl -fsSL <raw URL of this file> | bash      or copy it over and: bash setup-server.sh
# Installs Docker from Docker's own apt repository, opens ports 80 and 443 in the VM's firewall (Oracle's
# Ubuntu images block them), adds swap, and makes ~/careerfit for releases and the .env file.
set -euo pipefail

if ! command -v docker > /dev/null; then
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" |
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER"
fi

# Oracle's Ubuntu images reject everything but SSH in iptables, even when the cloud firewall allows it.
for port in 80 443; do
  sudo iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2> /dev/null ||
    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport "$port" -j ACCEPT
done
sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save

# 4 GB of swap, so a memory spike slows the server down instead of killing a container.
if [ ! -f /swapfile ]; then
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab > /dev/null
fi

mkdir -p ~/careerfit/releases
echo "Done. Log out and back in (for the docker group), then create ~/careerfit/.env from deploy/server.env.example."
