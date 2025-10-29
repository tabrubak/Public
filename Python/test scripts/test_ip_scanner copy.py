#!/usr/bin/env python3
"""
Interactive Ping + Port Scanner (sorted output)
- Enter a target (single IP/hostname or CIDR subnet, e.g. 192.168.1.0/24)
- Choose operations: ping, port scan, or both
- Enter ports as: "80", "22,80,443", or "1-1024"
- Results are printed and saved (if chosen) in sorted order
"""

import ipaddress
import platform
import subprocess
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
from datetime import datetime

# --------------------
# Helper utilities
# --------------------
def parse_ports(port_input):
    """Parse ports input like '22', '22,80,443', '1-1024' into a sorted list of ints."""
    ports = set()
    parts = [p.strip() for p in port_input.split(',') if p.strip()]
    for p in parts:
        if '-' in p:
            a, b = p.split('-', 1)
            try:
                a_i, b_i = int(a), int(b)
                if a_i > b_i:
                    a_i, b_i = b_i, a_i
                a_i = max(1, a_i)
                b_i = min(65535, b_i)
                ports.update(range(a_i, b_i + 1))
            except ValueError:
                continue
        else:
            try:
                pi = int(p)
                if 1 <= pi <= 65535:
                    ports.add(pi)
            except ValueError:
                continue
    return sorted(ports)

def expand_targets(target_input, max_hosts=512):
    """
    Accept either a single hostname/IP or a CIDR (e.g. 192.168.1.0/24)
    Returns a list of strings (hosts). Caps total hosts to max_hosts for safety.
    """
    target_input = target_input.strip()
    try:
        net = ipaddress.ip_network(target_input, strict=False)
        hosts = [str(h) for h in net.hosts()]
        if not hosts:
            hosts = [str(net.network_address)]
    except ValueError:
        hosts = [target_input]
    if len(hosts) > max_hosts:
        print(f"[!] Target expands to {len(hosts)} hosts — limiting to first {max_hosts} hosts for safety.")
        hosts = hosts[:max_hosts]
    return hosts

def host_sort_key(host):
    """Sort key that prefers numeric IP order when host is an IP, else falls back to string."""
    try:
        return (0, ipaddress.ip_address(host))
    except Exception:
        return (1, host.lower())

def ping_host(host, timeout=1000):
    """
    Ping a host once. Returns True if reachable, False otherwise.
    Uses platform-specific ping syntax.
    """
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout), host]
    else:
        cmd = ["ping", "-c", "1", host]
    try:
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=(timeout/1000 + 2) if system != "windows" else None)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False

def scan_port(host, port, tcp_timeout=1.0):
    """Return True if TCP port is open on host, else False."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(tcp_timeout)
            res = s.connect_ex((host, port))
            return res == 0
    except Exception:
        return False

# --------------------
# Interactive UI + Orchestration
# --------------------
def main():
    print("\n=== Interactive Ping + Port Scanner (sorted output) ===")
    target_input = input("Enter target (IP, hostname, or CIDR like 192.168.1.0/24): ").strip()
    if not target_input:
        print("No target provided, exiting.")
        sys.exit(0)

    hosts = expand_targets(target_input, max_hosts=512)
    hosts = sorted(hosts, key=host_sort_key)
    print(f"Resolved targets: {len(hosts)} host(s). Example: {hosts[:3]}{'...' if len(hosts)>3 else ''}")

    op = input("Operation: (p)ing, (s)can ports, (b)oth [p/s/b] (default b): ").strip().lower() or 'b'
    do_ping = op in ('p', 'b')
    do_scan = op in ('s', 'b')

    ports = []
    if do_scan:
        port_input = input("Enter ports (e.g. 22,80,443 or 1-1024). Default 22,80,443: ").strip() or "22,80,443"
        ports = parse_ports(port_input)
        if not ports:
            print("No valid ports parsed; exiting.")
            sys.exit(0)
        if len(ports) > 500:
            print(f"[!] You're about to scan {len(hosts)} hosts * {len(ports)} ports = potentially many checks.")
            ok = input("Continue? (y/N): ").strip().lower()
            if ok != 'y':
                print("Cancelled by user.")
                sys.exit(0)

    concurrency = input("Concurrency (number of worker threads, default 50): ").strip()
    try:
        max_workers = int(concurrency) if concurrency else 50
        max_workers = max(1, min(200, max_workers))
    except ValueError:
        max_workers = 50

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save = input("Save results to file? (y/N): ").strip().lower() == 'y'
    out_filename = f"scan_results_{timestamp}.txt" if save else None

    header = f"Scan started: {datetime.now().isoformat()}\nTarget: {target_input}\nHosts: {len(hosts)}\nPorts: {','.join(map(str, ports)) if ports else 'None'}\n"
    print("\n" + header)
    if save:
        with open(out_filename, "w") as f:
            f.write(header + "\n")

    results = []

    # Ping phase (collect then print sorted)
    reachable = set()
    ping_status = {}  # host -> 'UP'/'DOWN'
    if do_ping:
        print("-> Pinging hosts...")
        with ThreadPoolExecutor(max_workers=max_workers) as exc:
            future_to_host = {exc.submit(ping_host, h): h for h in hosts}
            for fut in as_completed(future_to_host):
                h = future_to_host[fut]
                try:
                    up = fut.result()
                except Exception:
                    up = False
                status = "UP" if up else "DOWN"
                ping_status[h] = status
                if up:
                    reachable.add(h)

        # print ping results in sorted order
        print("\n--- Ping results (sorted) ---")
        for h in sorted(ping_status.keys(), key=host_sort_key):
            line = f"{h}: {ping_status[h]}"
            print(line)
            results.append(line)
            if save:
                with open(out_filename, "a") as f:
                    f.write(line + "\n")

    # Port scan phase
    if do_scan:
        print("\n-> Scanning ports (this may take a moment)...")
        scan_hosts = hosts
        if do_ping:
            if reachable:
                scan_hosts = sorted(reachable, key=host_sort_key)
                print(f"Scanning {len(scan_hosts)} reachable host(s) (skipping hosts that pinged DOWN).")
            else:
                print("No hosts reported UP by ping; scanning all targets.")
                scan_hosts = hosts

        task_count = len(scan_hosts) * len(ports)
        print(f"Total checks: {task_count} (hosts {len(scan_hosts)} x ports {len(ports)})")

        open_ports_by_host = {}
        with ThreadPoolExecutor(max_workers=max_workers) as exc:
            future_to_hp = {}
            for h in scan_hosts:
                for p in ports:
                    future = exc.submit(scan_port, h, p, 1.0)
                    future_to_hp[future] = (h, p)

            for fut in as_completed(future_to_hp):
                h, p = future_to_hp[fut]
                try:
                    is_open = fut.result()
                except Exception:
                    is_open = False
                if is_open:
                    open_ports_by_host.setdefault(h, []).append(p)

        # Print sorted open-port lines as they are, and append to results/save
        print("\n--- Open ports (sorted) ---")
        if open_ports_by_host:
            for h in sorted(open_ports_by_host.keys(), key=host_sort_key):
                ps_sorted = sorted(open_ports_by_host[h])
                ports_str = ", ".join(map(str, ps_sorted))
                line = f"{h}: open ports -> {ports_str}"
                print(line)
                results.append(line)
                if save:
                    with open(out_filename, "a") as f:
                        f.write(line + "\n")
        else:
            line = "No open ports found for scanned hosts."
            print(line)
            results.append(line)
            if save:
                with open(out_filename, "a") as f:
                    f.write(line + "\n")

    # Final wrap-up (also sorted summary of everything for clarity)
    print("\n--- Final Summary (sorted) ---")
    # We'll present ping and port info combined per-host in sorted host order
    all_hosts_set = set(hosts)
    for h in sorted(all_hosts_set, key=host_sort_key):
        parts = [h]
        if do_ping:
            parts.append(ping_status.get(h, "UNKNOWN"))
        if do_scan:
            ports_for_h = open_ports_by_host.get(h, [])
            if ports_for_h:
                parts.append("open:" + ",".join(map(str, sorted(ports_for_h))))
            else:
                parts.append("open:none")
        line = " | ".join(parts)
        print(line)
        if save:
            with open(out_filename, "a") as f:
                f.write(line + "\n")

    footer = f"\nScan finished: {datetime.now().isoformat()}\n"
    print(footer)
    if save:
        with open(out_filename, "a") as f:
            f.write(footer)
        print(f"Results saved to: {out_filename}")

if __name__ == "__main__":
    main()
