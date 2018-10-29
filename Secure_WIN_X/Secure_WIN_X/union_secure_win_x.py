import ctypes
import configparser
import logging
import os
import platform
import subprocess
import winreg
from itertools import chain

import Test_con
from config_data import CONFIG_SECTIONS
from regkeys_data import REGKEYS_DICT, ValueEntry


def create_default_config(config, config_path):
    for section, options in sorted(CONFIG_SECTIONS.items()):
        config.add_section(section)
        if options is None:
            config.set(section, "disable", "no")
        else:
            for option in options:
                config.set(section, option, "no")
    with open(config_path, "w") as config_file:
        config.write(config_file)
    return config


def get_config(config_path):
    config = configparser.ConfigParser()
    config.BOOLEAN_STATES.update({"": False})
    if not os.path.exists(config_path):
        return create_default_config(config, config_path)
    try:
        config.read(config_path)
    except configparser.ParsingError as pars_err:
        print(f"Config file {config_path!r} contains errors:")
        for line_number, key_name in pars_err.errors:
            key_name = key_name.replace("\'", "").replace("\\n", "")
            print(f"\t[line {line_number}] Key {key_name!r} without value")
        raise
    for section in config:
        try:
            if section != "DEFAULT" and section not in CONFIG_SECTIONS:
                raise configparser.NoSectionError(section)
        except configparser.NoSectionError:
            print(f"Incorrect section name {section!r} in config file {config_path!r}."
                  f"\nAvailable sections names: {', '.join(name for name in CONFIG_SECTIONS)}")
            raise
    return config


def set_regkey_value(value_entry):
    opened_regkey = winreg.CreateKeyEx(
        value_entry.root_key, value_entry.subkey, 0, winreg.KEY_WOW64_64KEY + winreg.KEY_WRITE
    )
    winreg.SetValueEx(opened_regkey, value_entry.name, 0, value_entry.data_type, value_entry.data)
    winreg.CloseKey(opened_regkey)
    logging.info(f"Set {str(value_entry).lower()}")


def run_pwrshell_cmd(*args):
    logging.info(f"Run PowerShell command {' '.join(args)!r}")
    pwrshell_proc = subprocess.run(
        ["powershell", "-Command", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if not pwrshell_proc.returncode:
        logging.info(f"[OK] The exit status of last command is 0")
    else:
        logging.warning(f"[FAIL] The exit status of last command is non-zero")
    return pwrshell_proc


def run_shell_cmd(command):
    logging.info(f'Run command {command!r}')
    proc = subprocess.run(command.split(), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc


def disable_service(service_name):
    sc_proc = run_shell_cmd(f"sc.exe query {service_name}")
    if sc_proc.returncode != 1060:
        run_shell_cmd(f"sc.exe stop {service_name}")
        run_shell_cmd(f"sc.exe config {service_name} start=disabled")
        logging.info(f"Service {service_name!r} is disabled")
    else:
        logging.error(f"{service_name!r} does not exist as an installed service")


def delete_builtin_apps(config_options):
    Test_con.html_in("Удаленные приложения:",0)
    for app_name, delete in config_options:
        if delete:
            pwrshell_proc = run_pwrshell_cmd(fr'if ((Get-AppxPackage *{app.name}*)){{return 1}}else{{return 0}}')  # TODO: Remove-AppxPackage
            if(pwrshell_proc.stdout == b'1\r\n'):
                Test_con.html_in(app_name)
            elif(pwrshell_proc.stdout == b'0\r\n'): 
                Test_con.html_in(app_name, Param = False)
                Test_con.html_in("Такого приложения не найдено, уточните название.",2)
        else:
            Test_con.html_in(app_name, Param = False)
            Test_con.html_in("Отключено в конфигурационном файле",2)


def Out_microphone():
    Test_con.html_in("Выключение микрофона",0)
    PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture"
    aKey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, PATH, 0, winreg.KEY_WOW64_64KEY + winreg.KEY_READ)
    try:
        for j in range(winreg.QueryInfoKey(aKey)[0]):
            new_Key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, fr'{PATH}\{winreg.EnumKey(aKey,j)}', 0, winreg.KEY_WOW64_64KEY + winreg.KEY_READ)
            for i in range(winreg.QueryInfoKey(new_Key)[0]):
                try:
                    asubkey_name = winreg.EnumKey(new_Key, i)
                    asubkey = winreg.OpenKey(new_Key,asubkey_name)
                    val = winreg.QueryValueEx(asubkey, "{a45c254e-df1c-4efd-8020-67d146a850e0},2")
                    if (('Microphone' in val) or ('Микрофон' in val)):
                        # Добавил логирование
                        value_entry = ValueEntry(winreg.HKEY_LOCAL_MACHINE, fr"{PATH}\{winreg.EnumKey(aKey,j)}", "DeviceState", winreg.REG_DWORD, 10000001)
                        Key_for_delete = winreg.OpenKey(value_entry.root_key, value_entry.subkey, 0, winreg.KEY_WOW64_64KEY + winreg.KEY_SET_VALUE + winreg.KEY_READ)
                        winreg.SetValueEx(Key_for_delete, value_entry.name, 0, value_entry.data_type, value_entry.data)
                        logging.info(f"Set {str(value_entry).lower()}")
                        # Две строки ниже можно убрать, но пока оставил...
                        # winreg.CloseKey(Key_for_delete)
                        # Key_for_delete = winreg.OpenKeyEx(value_entry.root_key, value_entry.subkey, 0, winreg.KEY_WOW64_64KEY + winreg.KEY_READ)
                        if (winreg.QueryValueEx(Key_for_delete,"DeviceState")[0] == 10000001):
                            Test_con.html_in("Миркофон отключен")                  #10000001
                        else:
                            Test_con.html_in("Микрофон не отключен", Param = False)
                        winreg.CloseKey(Key_for_delete)
                except EnvironmentError as e:
                    print(e)
                except FileNotFoundError:
                    pass
    except WindowsError as e:
        logging.error(e)
        pass
    winreg.CloseKey(aKey)
    winreg.CloseKey(new_Key)


def Out_webcam():
    Test_con.html_in("Состояние Веб-камеры",0)
    Command_for_find_PnPDevice = 'if ((get-pnpDevice | where {{$_.FriendlyName -like "*Webcam*"}})){{return 1}}else{{return 0}}'
    Command_for_disabled_PnPDevice = '| Disable-PnpDevice'
    proc = subprocess.run(['powershell',fr'if ((get-pnpDevice | where {{$_.FriendlyName -like "*Webcam*"}})){{return 1}}else{{return 0}}'], stdout = subprocess.PIPE)
    if(proc.stdout == b'1\r\n'):
        #subprocess.run(['powershell',get-pnpDevice | where {{$_.FriendlyName -like "*Webcam*"}}{Command_for_disabled_PnPDevice}])
        Test_con.html_in("Веб-камера отключена успешно.")
    elif(proc.stdout == b'0\r\n'):
        Test_con.html_in("Устройство Веб-камеры не было найдено", Param = False)
    else:
        Test_con.html_in(proc.stdout,3)
    logging.info(proc.stdout)


def disable_powershell_scripts_execution():
    regkeys = REGKEYS_DICT.get("powershell")
    for regkey in regkeys.get("exec_policy"):
        set_regkey_value(regkey)


def disable_internet_explorer():
    dism_params = "/Online /Disable-Feature /FeatureName:Internet-Explorer-Optional-amd64 /NoRestart"
    run_shell_cmd(f"dism.exe {dism_params}")


def uninstall_onedrive():
    regkeys = REGKEYS_DICT.get("onedrive")
    run_shell_cmd("taskkill.exe /f /im OneDrive.exe")
    # Remove OneDrive
    is_64bit = True if platform.architecture()[0] == "64bit" else False
    sys_folder = "SysWOW64" if is_64bit else "System32"
    run_shell_cmd(os.path.expandvars(rf"%SystemRoot%\{sys_folder}\OneDriveSetup.exe /uninstall"))
    # Disable OneDrive via Group Policies
    for regkey in regkeys.get("group_policies"):
        set_regkey_value(regkey)
    # Remove Onedrive from explorer sidebar
    set_regkey_value(regkeys.get("explorer_sidebar").get("default"))
    if is_64bit:
        set_regkey_value(regkeys.get("explorer_sidebar").get("64bit"))
    # Removing startmenu entry
    run_pwrshell_cmd(
        "Remove-Item -Force -ErrorAction SilentlyContinue",
        os.path.expandvars(r"'%UserProfile%\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\OneDrive.lnk'")
    )
    # Removing scheduled task
    run_pwrshell_cmd(
        r"Get-ScheduledTask -TaskPath '\' -TaskName 'OneDrive*' -ErrorAction SilentlyContinue", "|",
        "Unregister-ScheduledTask -Confirm:$false"
    )


def disable_remote_access():
    regkeys = REGKEYS_DICT.get("remote_access")
    # Disable Remote Assistance
    for regkey in regkeys.get("remote_assistance"):
        set_regkey_value(regkey)
    # Disable Remote Desktop
    for regkey in regkeys.get("remote_desktop"):
        set_regkey_value(regkey)


def disable_location_and_sensors():
    regkeys = REGKEYS_DICT.get("location_and_sensors")
    for regkey in regkeys:
        set_regkey_value(regkey)


def disable_diagtracking_and_telemetry(config_options):
    regkeys = REGKEYS_DICT.get("diagtracking_and_telemetry")
    for option, disable in config_options:
        if disable:
            if option == "connected_user_experiences_and_telemetry":
                # Disable Diagnostics Tracking Service
                disable_service("DiagTrack")
                # Disable Microsoft Diagnostics Hub Standard Collector Service
                disable_service("diagnosticshub.standardcollector.service")
                # Disable WAP Push Message Routing Service
                disable_service("dmwappushservice")
            option_regkeys = regkeys.get(option)
            if isinstance(regkeys, dict):
                option_regkeys = chain(*option_regkeys.values())
            for regkey in option_regkeys:
                set_regkey_value(regkey)


if __name__ == "__main__":
    logrecord_format = "%(asctime)s | %(levelname)-8s | %(message)s"
    logging.basicConfig(filename="logfile.log", filemode="w", format=logrecord_format, level=logging.INFO)
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("Please run this program as administrator!")
        logging.critical("You need to run a program as administrator!")
        exit(1)
    else:
        Test_con.Init_html()
        # TODO: Add main config function
        try:
            config = get_config("config.cfg")
        except Exception:
            logging.critical("Unable to read config file")
        else:
            for section in CONFIG_SECTIONS:
                if config.has_section(section):
                    if section == 'DELETE_BUILTIN_APPS':
                        config_options = ((option, config[section].getboolean(option)) for option in config[section])
                        delete_builtin_apps(config_options)
                    elif section == 'DIAGNOSTIC_TRACKING_AND_TELEMETRY':
                        pass
                    elif section == 'INTERNET_EXPLORER':
                        pass
                    elif section == 'LOCATION_AND_SENSORS':
                        pass
                    elif section == 'MICROPHONE':
                        pass
                    elif section == 'ONEDRIVE':
                        pass
                    elif section == 'POWERSHELL_SCRIPTS_EXECUTION':
                        pass
                    elif section == 'REMOTE_ACCESS':
                        pass
                    elif section == 'WEBCAM':
                        pass
        Test_con.Out()