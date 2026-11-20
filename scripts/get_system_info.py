import os
import psutil
import platform
import subprocess
import json
from glob import glob
from pathlib import path

def get_base_env():
    info={
        "is_docker":os.path.exists('//.dockerenv'),
        "os_family":platform.system(),
        "os_name":""}
    if info["os_family"].lower() == "linux":
        try:
            with open("/etc/os-release", "r") as f:
                lines=f.readlines()
                for line in lines: 
                    if line.startswith("PRETTY_NAME="):
                        info["os_name"]=line.split("=")[1].strip().strip('"')
                        break
        except:
            info["os_name"].lower() == "generic linux"
    elif info["os_family"].lower() == "windows":
        info["os_name"]=f"Windows {platform.release()}"
    return info

def get_ram_info(env):
    if env["os_family"].lower() == "linux":
        try:
            with open('/proc/meminfo', "r") as f:
                for line in f:
                    if "MemTotal" in line:
                        kb=int(line.split()[1])
                        return f"{round(kb/(1024**2))} GB"
        except:
            return "Unknown RAM"
    elif env["os_family"].lower() == "windows":
        try:
            output=subprocess.check_output("wmic computersystem get totalphysicalmemory", shell=True).decode()
            bytes_val=int(output.split('\n')[1].strip())
            return f"{round(bytes_val/(1024**3))} GB"
        except:
            return "Unknown RAM"
    return "Unknown RAM"

def get_gpu_info(env):
    if env["os_family"].lower() == "windows":
        try:
            gpu_info=subprocess.chek_output('wmic path win32_Video_controller get name', shell=True).decode('cp1251', errors='ignore')
            return gpu_info.split('\n')[1].strip()
        except: pass
    elif env["os_family"].lower() == "linux":
        try:
            gpu_info=subprocess.check_output("lspci | grep -E 'VGA|3D'", shell=True).decode()
            return gpu_info.split(":")[-1].strip()
        except Exception as e:
            print(e)
            return get_linux_gpu_universal()

def get_linux_gpu_universal():
    vendors={
        "0x1002":"AMD",
        "0x10de":"NVIDIA",
        "0x8086":"Intel"}
    gpu_list=[]
    path="/sys/class/drm/"
    if not os.path.exists(path):
        return "Unknown GPU (DRM not found)"
    try:
        cards=[d for d in os.listdir(path) if d.startswith("card") and "-" not in d]
        for card in cards:
            vendor_path=os.path.join(path, card, "device/vendor")
            print(vendor_path)
            device_path=os.path.join(path, card, "device/device")
            print(device_path)
            if os.path.exists(vendor_path):
                with open(vendor_path, "r") as f:
                    v_id=f.read().strip().lower()
                print(v_id)
                vendor_name=vendors.get(v_id, f"Unknown ({v_id})")
                print(vendor_name)
                gpu_list.append(f"{vendor_name} GPU ({card})")
        return ",".join(gpu_list) if gpu_list else "Unknown GPU"
    except Exception as e:
        return f"Unknown GPU (Error reading sysfs) {e}"

def get_cpu_info(env):
    if env["os_family"].lower() == "windows":
        try:
            output=subprocess.check_output("wmic cpu get name", shell=True).decode()
            return output.split("\n")[1].strip()
        except Exception:
            return platform.processor() or "Unknown CPU"
    elif env["os_family"].lower() == "linux":
        try:
            with open("/proc/cpuinfo" ,"r") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":")[1].strip()
        except Exception:
            return "Unknown CPU"
    return "Unknown CPU"

def get_container_resources():
    res={"CPU_limit":"Unset", "RAM_limit":"Unset"}
    try:
        path="/sys/fs/cgroup/memory/memory.limit_in_bytes"
        if not os.path.exists(path):
            path="/sys/fs/cgroup/memory.max"

        with open(path, "r") as f:
            val=f.read().strip()
            if val != "max" and int(val)<0x7FFFFFFFFFFFFFFF:
                res["RAM_limit"]=f"{round(int(val)/(1024**3))}GB"
    except: pass

    try:
        res["CPU_limit"]=f"{os.cpu_count()} Cores"
    except: pass

    return res

def get_hardware_specs():
    specs={"CPU":"Unknown", "GPU":"Unknown", "RAM":"Unknown"}
    docker_res={"CPU_limit":"Unset", "RAM_limit":"Unset"}
    env=get_base_env()
    if env["is_docker"]:
        docker_res=get_container_resources()
        specs["RAM"]=get_ram_info({"os_family":"Linux"})
        specs["CPU"]=get_cpu_info({"os_family":"Linux"})
        specs["GPU"]=get_gpu_info({"os_family":"Linux"})
    else:
        specs["RAM"]=get_ram_info(env)
        specs["GPU"]=get_gpu_info(env)
        specs["CPU"]=get_cpu_info(env)
    return env,specs,docker_res

def _cgroup_memory():
    """Return (limit, used) in bytes for this cgroup, or (None, None)."""
    candidates = (
        ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory.current"),
        ("/sys/fs/cgroup/memory/memory.limit_in_bytes",
         "/sys/fs/cgroup/memory/memory.usage_in_bytes"),
    )
    for limit_path, used_path in candidates:
        try:
            raw = Path(limit_path).read_text().strip()
            used = int(Path(used_path).read_text().strip())
        except (OSError, ValueError):
            continue
        if raw == "max" or int(raw) >= 1 << 60:
            return None, None  # no real limit
        return int(raw), used
    return None, None


def _vram_amdgpu():
    """(total, free) of the AMD GPU with the most VRAM, or None."""
    best = None
    for device in glob("/sys/class/drm/card?/device"):
        try:
            total = int(Path(device, "mem_info_vram_total").read_text())
            used = int(Path(device, "mem_info_vram_used").read_text())
        except (OSError, ValueError):
            continue
        if best is None or total > best[0]:
            best = (total, total - used)
    return best


def _vram_nvidia():
    """(total, free) of the NVIDIA GPU with the most VRAM, or None."""
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total,memory.free",
             "--format=csv,noheader,nounits"],
            timeout=5, text=True,
        )
        rows = [
            tuple(int(x) * 1024**2 for x in line.split(","))
            for line in output.strip().splitlines()
        ]
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return max(rows) if rows else None


def get_memory_status() -> dict:
    """Live memory numbers in bytes; None where they cannot be read."""
    ram = psutil.virtual_memory()
    total, available = ram.total, ram.available

    limit, used = _cgroup_memory()
    if limit is not None:  # inside a container with a memory limit
        total = min(total, limit)
        available = min(available, max(limit - used, 0))

    source = "amdgpu-sysfs"
    vram = _vram_amdgpu()
    if vram is None:
        source, vram = "nvidia-smi", _vram_nvidia()
    if vram is None:
        source = None

    return {
        "ram_total": total,
        "ram_available": available,
        "vram_total": vram[0] if vram else None,
        "vram_free": vram[1] if vram else None,
        "gpu_source": source,
    }

