#!/usr/bin/env bash
# Build a downloadable QEMU demo disk. Run on a disposable Linux runner.
set -euo pipefail
source_dir=$(cd "$(dirname "$0")/.." && pwd)
out="$PWD/nura-vm"
work=$(mktemp -d)
mkdir -p "$out"
trap 'if [[ -n ${pid:-} ]]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi; rm -rf "$work"' EXIT
cd "$work"

base_url=https://cloud-images.ubuntu.com/noble/current
base=noble-server-cloudimg-amd64.img
curl -fsSLo "$base" "$base_url/$base"
curl -fsSLo SHA256SUMS "$base_url/SHA256SUMS"
grep -E "[ *]$base$" SHA256SUMS | sha256sum --check
qemu-img create -f qcow2 -F qcow2 -b "$work/$base" work.qcow2
qemu-img resize work.qcow2 8G
cp /usr/share/OVMF/OVMF_CODE_4M.fd "$out/OVMF_CODE_4M.fd"
cp /usr/share/OVMF/OVMF_VARS_4M.fd "$out/OVMF_VARS_4M.fd"

mkdir -p payload
cp -r "$source_dir/src" "$source_dir/assets" "$source_dir/vm" payload/
tar -czf nura.tgz -C payload .
printf 'instance-id: nura-vm\nlocal-hostname: nura-vm\n' >meta-data
cat >user-data <<'EOF'
#cloud-config
package_update: true
packages:
  - xserver-xorg-core
  - xserver-xorg-input-libinput
  - xinit
  - python3-cairo
  - python3-tk
  - python3-pil.imagetk
  - fonts-dejavu-core
write_files:
  - path: /etc/systemd/system/nura-vm.service
    permissions: '0644'
    content: |
      [Unit]
      Description=NURA OS desktop for QEMU
      After=systemd-user-sessions.service

      [Service]
      RuntimeDirectory=nura-vm
      ExecStartPre=/usr/bin/chown nura:nura /run/nura-vm
      ExecStart=/usr/bin/xinit /usr/sbin/runuser -u nura -- /usr/bin/python3 -B /opt/nura/vm/nura-desktop.py -- /usr/bin/Xorg :0 vt7 -keeptty -nolisten tcp -ac
      ExecStartPost=/bin/sh -c 'for i in $(seq 1 60); do if [ -f /run/nura-vm/ready ]; then echo NURA_VM_READY > /dev/ttyS0; exit 0; fi; sleep 1; done; exit 1'

      [Install]
      WantedBy=multi-user.target
runcmd:
  - [adduser, --disabled-password, --gecos, '', nura]
  - [mkdir, -p, /mnt/nura-seed, /opt/nura]
  - [mount, -o, ro, LABEL=cidata, /mnt/nura-seed]
  - [tar, -xzf, /mnt/nura-seed/nura.tgz, -C, /opt/nura]
  - [umount, /mnt/nura-seed]
  - [systemctl, daemon-reload]
  - [systemctl, enable, --now, nura-vm.service]
EOF
genisoimage -quiet -output seed.iso -volid cidata -joliet -rock user-data meta-data nura.tgz

qemu-system-x86_64 -m 3072 -smp 4 -machine q35 -cpu max \
  -drive "if=pflash,format=raw,readonly=on,file=$out/OVMF_CODE_4M.fd" \
  -drive "if=pflash,format=raw,file=$out/OVMF_VARS_4M.fd" \
  -drive if=virtio,format=qcow2,file=work.qcow2 \
  -drive media=cdrom,format=raw,file=seed.iso \
  -nic user,model=virtio-net-pci -device qemu-xhci -device usb-tablet \
  -display none -serial file:serial.log -monitor unix:monitor.sock,server,nowait &
pid=$!

wait_for_desktop() {
  for ((i=0;i<240;i++)); do
    if grep -q NURA_VM_READY serial.log 2>/dev/null; then return; fi
    kill -0 "$pid"
    sleep 3
  done
  tail -100 serial.log
  return 1
}
poweroff_vm() {
  printf 'system_powerdown\n' | socat - UNIX-CONNECT:monitor.sock
  for ((i=0;i<90;i++)); do
    if ! kill -0 "$pid" 2>/dev/null; then wait "$pid"; pid=; return; fi
    sleep 2
  done
  return 1
}
wait_for_desktop
poweroff_vm
qemu-img convert -c -O qcow2 work.qcow2 "$out/nura-os.qcow2"
qemu-img check "$out/nura-os.qcow2"

# Boot a temporary overlay of the exported disk with no installer ISO.
qemu-img create -f qcow2 -F qcow2 -b "$out/nura-os.qcow2" smoke.qcow2
cp /usr/share/OVMF/OVMF_VARS_4M.fd smoke-vars.fd
rm -f serial.log monitor.sock
qemu-system-x86_64 -m 3072 -smp 4 -machine q35 -cpu max \
  -drive "if=pflash,format=raw,readonly=on,file=$out/OVMF_CODE_4M.fd" \
  -drive if=pflash,format=raw,file=smoke-vars.fd \
  -drive if=virtio,format=qcow2,file=smoke.qcow2 \
  -nic none -device qemu-xhci -device usb-tablet \
  -display none -serial file:serial.log -monitor unix:monitor.sock,server,nowait &
pid=$!
wait_for_desktop
poweroff_vm
cp /usr/share/OVMF/OVMF_VARS_4M.fd "$out/OVMF_VARS_4M.fd"
cat >"$out/README.txt" <<'EOF'
NURA OS para QEMU x86_64

Extraia o ZIP. Em um computador com QEMU, execute na pasta extraida:

qemu-system-x86_64 -machine q35 -m 3072 -smp 4 -drive if=pflash,format=raw,readonly=on,file=OVMF_CODE_4M.fd -drive if=pflash,format=raw,file=OVMF_VARS_4M.fd -drive if=virtio,format=qcow2,file=nura-os.qcow2 -device qemu-xhci -device usb-tablet -nic none

O NURA abre automaticamente. Use mouse e teclado. Esc sai da tela cheia.
Para desligar pelo monitor do QEMU: Ctrl+Alt+2 e system_powerdown.
O disco usa Ubuntu x86_64 e UEFI.
O disco e para VM; o kernel e os drivers do NX591J nao fazem parte dele.
EOF
(cd "$out" && sha256sum nura-os.qcow2 > SHA256SUMS)
