###############################################################################
#                                                                             #  
# @file: create_user.py                                                       #  
# @description: Script to create Airflow users from configuration file        #
# @date: May 2025                                                             #
# @version: 2.0                                                               #  
#                                                                             #  
# This script reads user configuration from an INI file and creates an        #
# Airflow user with the specified credentials and role. It automates the      #
# process of setting up users in Airflow by using the command-line interface. #
#                                                                             #  
###############################################################################

import configparser
import subprocess
from airflow.models.variable import Variable

def create_user_from_ini(ini_file):
    """
    Create an Airflow user using credentials from an INI configuration file.
    
    This function reads user details from the specified INI file and uses
    the Airflow CLI to create a user with those credentials.
    
    Args:
        ini_file (str): Path to the INI file containing user configuration
    """
    # OBJECTIVE: Parse the configuration file
    config = configparser.ConfigParser()
    config.read("/opt/airflow/dags/airflow.cfg") 

    # OBJECTIVE: Extract user details from the config
    # Get values from the USER section of the INI file
    user_data = config["user"] 
    
    # Extract specific user attributes with defaults where appropriate
    username = user_data.get("username")
    firstname = user_data.get("firstname")
    lastname = user_data.get("lastname")
    email = user_data.get("email")
    password = user_data.get("password")
    role = user_data.get("role", "Admin")  # Default role is Admin if not specified

    # OBJECTIVE: Create the user via Airflow CLI
    # Use subprocess to run the Airflow command-line interface
    subprocess.run(
        [
            "airflow",              # Command
            "users",                # Subcommand for user management
            "create",               # Action to create a new user
            "--username", username,
            "--firstname", firstname,
            "--lastname", lastname,
            "--role", role,
            "--email", email,
            "--password", password,
        ],
        check=True,  # Raise an exception if the command fails
    )
    
    # Log success message
    print(f"User '{username}' created successfully.")

    # OBJECTIVE: Set Airflow Variable for notification email
    # Use Variable.set() to store the email in the Airflow database
    try:
        Variable.set(key="notification_email", value=email)
        print(f"Airflow Variable 'notification_email' set to '{email}'.")
    except Exception as e:
        print(f"Error setting Airflow Variable 'notification_email': {e}")

# OBJECTIVE: Execute the script if run directly
if __name__ == "__main__":
    # Path to the Airflow configuration file containing user details
    create_user_from_ini("/opt/airflow/dags/airflow.ini")