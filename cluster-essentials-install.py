import os
import subprocess

FORCE_COLOR = 0
ns_name = "tanzu-cluster-essentials"

install_bundle = os.environ.get("INSTALL_BUNDLE", "")
install_registry_hostname = os.environ.get("INSTALL_REGISTRY_HOSTNAME", "")
install_registry_username = os.environ.get("INSTALL_REGISTRY_USERNAME", "")
install_registry_password = os.environ.get("INSTALL_REGISTRY_PASSWORD", "")

if not install_bundle:
    print("INSTALL_BUNDLE env var must not be empty")
    exit(1)
if not install_registry_hostname:
    print("INSTALL_REGISTRY_HOSTNAME env var must not be empty")
    exit(1)
if not install_registry_username:
    print("INSTALL_REGISTRY_USERNAME env var must not be empty")
    exit(1)
if not install_registry_password:
    print("INSTALL_REGISTRY_PASSWORD env var must not be empty")
    exit(1)

print(f"## Creating namespace {ns_name}")
create_namespace_command = f"kubectl create ns {ns_name} --dry-run=client -oyaml | kubectl apply -f-"
namespace_process = subprocess.run(create_namespace_command, shell=True)
if namespace_process.returncode != 0:
    print("Failed to create namespace")
    exit(1)

print(f"## Pulling bundle from {install_registry_hostname} (username: {install_registry_username})")
imgpkg_pull_command = f"imgpkg pull -b {install_bundle} -o ./bundle/"
imgpkg_process = subprocess.run(imgpkg_pull_command, shell=True)
if imgpkg_process.returncode != 0:
    print("Failed to fetch bundle")
    exit(1)

ytt_registry_server = install_registry_hostname
ytt_registry_username = install_registry_username
ytt_registry_password = install_registry_password

print("## Deploying kapp-controller")
ytt_kapp_command = (
    f"ytt -f ./bundle/kapp-controller/config/ -f ./bundle/registry-creds/ "
    f"--data-values-env YTT --data-value-yaml kappController.deployment.concurrency=10 | "
    f"kbld -f- -f ./bundle/.imgpkg/images.yml | "
    f"kapp deploy -a kapp-controller -n {ns_name} -f- --yes"
)
ytt_kapp_process = subprocess.run(ytt_kapp_command, shell=True)
if ytt_kapp_process.returncode != 0:
    print("Failed to deploy kapp-controller")
    exit(1)

print("## Deploying secretgen-controller")
ytt_secretgen_command = (
    f"ytt -f ./bundle/secretgen-controller/config/ -f ./bundle/registry-creds/ "
    f"--data-values-env YTT | "
    f"kbld -f- -f ./bundle/.imgpkg/images.yml | "
    f"kapp deploy -a secretgen-controller -n {ns_name} -f- --yes"
)
ytt_secretgen_process = subprocess.run(ytt_secretgen_command, shell=True)
if ytt_secretgen_process.returncode != 0:
    print("Failed to deploy secretgen-controller")
    exit(1)
