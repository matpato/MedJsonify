import configparser
import subprocess

def create_user_from_ini(ini_file):
    config = configparser.ConfigParser()
    config.read(ini_file)

    user_data = config["USER"]
    
    username = user_data.get("username")
    firstname = user_data.get("firstname")
    lastname = user_data.get("lastname")
    email = user_data.get("email")
    password = user_data.get("password")
    role = user_data.get("role", "Admin")

    subprocess.run(
        [
            "airflow",
            "users",
            "create",
            "--username",
            username,
            "--firstname",
            firstname,
            "--lastname",
            lastname,
            "--role",
            role,
            "--email",
            email,
            "--password",
            password,
        ],
        check=True,
    )
    print(f"User '{username}' created successfully.")

if __name__ == "__main__":
    create_user_from_ini("/opt/airflow/dags/airflow.ini")
