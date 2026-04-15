import os
import psutil
import platform
import subprocess
import json

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

def get_gpu_specs(env):
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

def get_hardware_specs(env):
    specs={"cpu":"Unknown", "gpu":"Unknown", "RAM":"Unknown"}
    if env["is_docker"]:
        print("In docker") 
    else:
        specs["RAM"]=get_ram_info(env)
        specs["gpu"]=get_gpu_specs(env)
        specs["cpu"]=get_cpu_info(env)
    return specs
env=get_base_env()
print(get_hardware_specs(env))
