#!/usr/bin/env python3
import argparse
import os
import subprocess
import requests
import json


def cprint(*args, level: int = 1):
    """
    logs colorful messages
    level = 1 : RED
    level = 2 : GREEN
    level = 3 : YELLOW

    default level = 1
    """
    CRED = "\033[31m"
    CGRN = "\33[92m"
    CYLW = "\33[93m"
    reset = "\033[0m"
    message = " ".join(map(str, args))
    if level == 1:
        print(CRED, message, reset)  # noqa: T001, T201
    if level == 2:
        print(CGRN, message, reset)  # noqa: T001, T201
    if level == 3:
        print(CYLW, message, reset)  # noqa: T001, T201


def get_available_branches(repo_url):
    """
    Get available branches from a GitHub repository
    """
    try:
        # Extract owner and repo from GitHub URL
        if repo_url.startswith("https://github.com/"):
            parts = repo_url.replace("https://github.com/", "").split("/")
            if len(parts) >= 2:
                owner, repo = parts[0], parts[1]
                api_url = f"https://api.github.com/repos/{owner}/{repo}/branches"
                response = requests.get(api_url, timeout=10)
                if response.status_code == 200:
                    branches = [branch["name"] for branch in response.json()]
                    return branches
    except Exception as e:
        cprint(f"Warning: Could not fetch branches from {repo_url}: {e}", level=3)
    
    # Fallback: try git ls-remote
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", repo_url],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            branches = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split()
                    if len(parts) >= 2:
                        branch_name = parts[1].replace('refs/heads/', '')
                        branches.append(branch_name)
            return branches
    except Exception as e:
        cprint(f"Warning: Could not fetch branches using git ls-remote: {e}", level=3)
    
    return []


def validate_branch(repo_url, branch):
    """
    Validate if a branch exists in the repository
    """
    available_branches = get_available_branches(repo_url)
    if available_branches:
        if branch in available_branches:
            return True
        else:
            cprint(f"Error: Branch '{branch}' not found in repository {repo_url}", level=1)
            cprint(f"Available branches: {', '.join(available_branches)}", level=3)
            return False
    else:
        cprint(f"Warning: Could not validate branch '{branch}' - proceeding anyway", level=3)
        return True


def main():
    parser = get_args_parser()
    args = parser.parse_args()
    
    # Validate branch before proceeding
    if not validate_branch(args.frappe_repo, args.frappe_branch):
        cprint("Please specify a valid branch using --frappe-branch", level=1)
        return
    
    init_bench_if_not_exist(args)
    create_site_in_bench(args)


def get_args_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-j",
        "--apps-json",
        action="store",
        type=str,
        help="Path to apps.json, default: apps-example.json",
        default="apps-example.json",
    )  # noqa: E501
    parser.add_argument(
        "-b",
        "--bench-name",
        action="store",
        type=str,
        help="Bench directory name, default: frappe-bench",
        default="frappe-bench",
    )  # noqa: E501
    parser.add_argument(
        "-s",
        "--site-name",
        action="store",
        type=str,
        help="Site name, should end with .localhost, default: development.localhost",  # noqa: E501
        default="development.localhost",
    )
    parser.add_argument(
        "-r",
        "--frappe-repo",
        action="store",
        type=str,
        help="frappe repo to use, default: https://github.com/sin-ev/backend",  # noqa: E501
        default="https://github.com/sin-ev/backend",
    )
    parser.add_argument(
        "-t",
        "--frappe-branch",
        action="store",
        type=str,
        help="frappe branch to use, default: version-12",  # noqa: E501
        default="version-12",  # Changed from version-15 to version-12
    )
    parser.add_argument(
        "-p",
        "--py-version",
        action="store",
        type=str,
        help="python version, default: Not Set",  # noqa: E501
        default=None,
    )
    parser.add_argument(
        "-n",
        "--node-version",
        action="store",
        type=str,
        help="node version, default: Not Set",  # noqa: E501
        default=None,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="verbose output",  # noqa: E501
    )
    parser.add_argument(
        "-a",
        "--admin-password",
        action="store",
        type=str,
        help="admin password for site, default: 123",  # noqa: E501
        default="123",
    )
    parser.add_argument(
        "-d",
        "--db-type",
        action="store",
        type=str,
        help="Database type to use (e.g., mariadb or postgres)",
        default="postgres",  # Changed default to postgres
    )
    parser.add_argument(
        "--list-branches",
        action="store_true",
        help="List available branches in the Frappe repository",
    )
    return parser


def init_bench_if_not_exist(args):
    if os.path.exists(args.bench_name):
        cprint("Bench already exists. Only site will be created", level=3)
        return
    
    try:
        env = os.environ.copy()
        if args.py_version:
            env["PYENV_VERSION"] = args.py_version
        
        init_command = ""
        if args.node_version:
            init_command = f"nvm use {args.node_version};"
        if args.py_version:
            init_command += f"PYENV_VERSION={args.py_version} "
        init_command += "bench init "
        init_command += "--skip-redis-config-generation "
        init_command += "--verbose " if args.verbose else " "
        init_command += f"--frappe-path={args.frappe_repo} "
        init_command += f"--frappe-branch={args.frappe_branch} "
        init_command += f"--apps_path={args.apps_json} "
        init_command += args.bench_name
        
        cprint(f"Initializing bench with Frappe branch: {args.frappe_branch}", level=2)
        
        command = [
            "/bin/bash",
            "-i",
            "-c",
            init_command,
        ]
        
        result = subprocess.run(command, env=env, cwd=os.getcwd(), capture_output=True, text=True)
        
        if result.returncode != 0:
            cprint("Error during bench initialization:", level=1)
            cprint(result.stderr, level=1)
            if "InvalidRemoteException" in result.stderr:
                cprint("This error usually means the specified branch doesn't exist.", level=1)
                cprint("Use --list-branches to see available branches.", level=3)
            return
        
        cprint("Configuring Bench ...", level=2)
        cprint("Set db_host", level=3)
        if args.db_type:
            cprint(f"Setting db_type to {args.db_type}", level=3)
            subprocess.call(
                ["bench", "set-config", "-g", "db_type", args.db_type],
                cwd=os.path.join(os.getcwd(), args.bench_name),
            )

        cprint("Set redis_cache to redis://redis-cache:6379", level=3)
        subprocess.call(
            [
                "bench",
                "set-config",
                "-g",
                "redis_cache",
                "redis://redis-cache:6379",
            ],
            cwd=os.path.join(os.getcwd(), args.bench_name),
        )
        cprint("Set redis_queue to redis://redis-queue:6379", level=3)
        subprocess.call(
            [
                "bench",
                "set-config",
                "-g",
                "redis_queue",
                "redis://redis-queue:6379",
            ],
            cwd=os.path.join(os.getcwd(), args.bench_name),
        )
        cprint(
            "Set redis_socketio to redis://redis-queue:6379 for backward compatibility",  # noqa: E501
            level=3,
        )
        subprocess.call(
            [
                "bench",
                "set-config",
                "-g",
                "redis_socketio",
                "redis://redis-queue:6379",
            ],
            cwd=os.path.join(os.getcwd(), args.bench_name),
        )
        cprint("Set developer_mode", level=3)
        subprocess.call(
            ["bench", "set-config", "-gp", "developer_mode", "1"],
            cwd=os.path.join(os.getcwd(), args.bench_name),
        )
    except subprocess.CalledProcessError as e:
        cprint(f"Error during bench initialization: {e}", level=1)


def create_site_in_bench(args):
    if args.db_type == "mariadb":
        cprint("Set db_host", level=3)
        subprocess.call(
            ["bench", "set-config", "-g", "db_host", "mariadb"],
            cwd=os.path.join(os.getcwd(), args.bench_name),
        )
        new_site_cmd = [
            "bench",
            "new-site",
            f"--db-root-username=root",
            f"--db-host=mariadb",  # Should match the compose service name
            f"--db-type={args.db_type}",  # Add the selected database type
            f"--mariadb-user-host-login-scope=%",
            f"--db-root-password=123",  # Replace with your MariaDB password
            f"--admin-password={args.admin_password}",
        ]
    else:
        # PostgreSQL configuration
        cprint("Set db_host", level=3)
        subprocess.call(
            ["bench", "set-config", "-g", "db_host", "postgresql"],
            cwd=os.path.join(os.getcwd(), args.bench_name),
        )
        new_site_cmd = [
            "bench",
            "new-site",
            f"--db-root-username=postgres",  # PostgreSQL default superuser
            f"--db-host=postgresql",  # Should match the compose service name
            f"--db-type={args.db_type}",  # PostgreSQL database type
            f"--db-root-password=123",  # PostgreSQL password
            f"--admin-password={args.admin_password}",
        ]
    
    apps = os.listdir(f"{os.getcwd()}/{args.bench_name}/apps")
    apps.remove("frappe")
    for app in apps:
        new_site_cmd.append(f"--install-app={app}")
    new_site_cmd.append(args.site_name)
    cprint(f"Creating Site {args.site_name} ...", level=2)
    subprocess.call(
        new_site_cmd,
        cwd=os.path.join(os.getcwd(), args.bench_name),
    )


if __name__ == "__main__":
    parser = get_args_parser()
    args = parser.parse_args()
    
    # Handle --list-branches option
    if args.list_branches:
        cprint(f"Fetching available branches from {args.frappe_repo}...", level=2)
        branches = get_available_branches(args.frappe_repo)
        if branches:
            cprint("Available branches:", level=2)
            for branch in sorted(branches):
                cprint(f"  - {branch}", level=3)
        else:
            cprint("Could not fetch branches. Please check the repository URL.", level=1)
    else:
        main()
