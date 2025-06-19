import argparse
import logging
import random
import json
import yaml
import os
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def setup_argparse():
    """
    Sets up the argument parser for the misconfig-ConfigMutationTester tool.

    Returns:
        argparse.ArgumentParser: The argument parser object.
    """
    parser = argparse.ArgumentParser(
        description="Randomly mutates configuration values to assess system resilience and identify vulnerabilities."
    )
    parser.add_argument(
        "config_file",
        help="Path to the configuration file (YAML or JSON).",
        type=str
    )
    parser.add_argument(
        "-m",
        "--mutation_rate",
        type=float,
        default=0.1,
        help="The probability (0.0 to 1.0) of mutating each configuration value. Default: 0.1",
    )
    parser.add_argument(
        "-o",
        "--output_file",
        type=str,
        help="Path to save the mutated configuration file. If not provided, overwrites the original file.",
    )
    parser.add_argument(
        "-t",
        "--test_command",
        type=str,
        help="Command to execute with the mutated configuration.  Example: 'my_app --config {}'",
    )
    parser.add_argument(
        "--lint",
        action="store_true",
        help="Run yamllint/jsonlint on the mutated config file before testing.",
    )
    return parser


def load_config(config_file):
    """
    Loads a configuration file (YAML or JSON) into a Python dictionary.

    Args:
        config_file (str): Path to the configuration file.

    Returns:
        dict: A dictionary representing the configuration.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        ValueError: If the file type is not supported.
        yaml.YAMLError: If the YAML file is invalid.
        json.JSONDecodeError: If the JSON file is invalid.
    """
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    try:
        with open(config_file, "r") as f:
            if config_file.endswith((".yaml", ".yml")):
                config = yaml.safe_load(f)
            elif config_file.endswith(".json"):
                config = json.load(f)
            else:
                raise ValueError("Unsupported configuration file type.  Must be YAML or JSON.")
        return config
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML file: {e}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON file: {e}")
        raise


def save_config(config, output_file):
    """
    Saves the configuration to a file (YAML or JSON).

    Args:
        config (dict): The configuration dictionary.
        output_file (str): Path to save the configuration file.

    Raises:
        ValueError: If the file type is not supported.
        Exception: If there are issues writing to the file.
    """
    try:
        with open(output_file, "w") as f:
            if output_file.endswith((".yaml", ".yml")):
                yaml.dump(config, f, indent=2)  # Use indent for readability
            elif output_file.endswith(".json"):
                json.dump(config, f, indent=2) # Use indent for readability
            else:
                raise ValueError("Unsupported configuration file type. Must be YAML or JSON.")

        logging.info(f"Mutated configuration saved to: {output_file}")

    except Exception as e:
        logging.error(f"Error writing configuration to file: {e}")
        raise


def mutate_value(value):
    """
    Mutates a single configuration value randomly.

    Args:
        value: The configuration value to mutate.

    Returns:
        The mutated value.
    """
    # Supported data types and their mutation strategies
    if isinstance(value, str):
        # Mutate string by adding or removing characters
        if random.random() < 0.5:
            # Add random characters
            chars = "abcdefghijklmnopqrstuvwxyz0123456789"
            num_chars = random.randint(1, 5)
            value += ''.join(random.choice(chars) for _ in range(num_chars))
        else:
            # Remove some chars, if possible
            if len(value) > 2:
                num_chars_to_remove = random.randint(1, len(value) // 2)
                start_index = random.randint(0, len(value) - num_chars_to_remove)
                value = value[:start_index] + value[start_index + num_chars_to_remove:]
            else:
                value = ""
    elif isinstance(value, int):
        # Mutate integer by adding or subtracting a small random value
        mutation_amount = random.randint(-5, 5)
        value += mutation_amount
    elif isinstance(value, float):
        # Mutate float by adding or subtracting a small random value
        mutation_amount = random.uniform(-0.5, 0.5)
        value += mutation_amount
    elif isinstance(value, bool):
        # Mutate boolean by flipping the value
        value = not value
    else:
        # For unsupported types, log a warning and return the original value.
        logging.warning(f"Unsupported data type for mutation: {type(value)}. Returning original value.")
        return value
    return value


def mutate_config(config, mutation_rate):
    """
    Recursively mutates a configuration dictionary based on the given mutation rate.

    Args:
        config (dict): The configuration dictionary.
        mutation_rate (float): The probability of mutating each configuration value.

    Returns:
        dict: The mutated configuration dictionary.
    """
    for key, value in config.items():
        if isinstance(value, dict):
            # Recursively mutate nested dictionaries
            config[key] = mutate_config(value, mutation_rate)
        elif random.random() < mutation_rate:
            # Mutate the value based on its data type
            config[key] = mutate_value(value)
    return config


def run_test_command(config_file, test_command):
    """
    Runs a test command with the mutated configuration file.

    Args:
        config_file (str): Path to the mutated configuration file.
        test_command (str): The test command to execute, with '{}' as a placeholder for the config file path.
    """
    try:
        command = test_command.format(config_file)
        logging.info(f"Executing test command: {command}")
        result = subprocess.run(command, shell=True, capture_output=True, text=True)

        logging.info(f"Command output:\n{result.stdout}")
        if result.stderr:
            logging.error(f"Command error:\n{result.stderr}")
        logging.info(f"Command return code: {result.returncode}")
        return result.returncode

    except Exception as e:
        logging.error(f"Error executing test command: {e}")
        return -1  # Indicate an error


def lint_config(config_file):
    """
    Lints a configuration file using yamllint or jsonlint, depending on the file type.
    """
    try:
        if config_file.endswith((".yaml", ".yml")):
            # Yamllint
            result = subprocess.run(["yamllint", config_file], capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"yamllint found errors:\n{result.stderr}")
                return False
            else:
                logging.info("yamllint passed successfully.")
                return True

        elif config_file.endswith(".json"):
            # jsonlint
            result = subprocess.run(["jsonlint", config_file], capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"jsonlint found errors:\n{result.stderr}")
                return False
            else:
                logging.info("jsonlint passed successfully.")
                return True
        else:
            logging.warning("Unsupported file type for linting.  Skipping linting.")
            return True  # Skip if not yaml or json

    except FileNotFoundError as e:
         logging.error(f"Linting tool not found: {e}")
         return False
    except Exception as e:
        logging.error(f"Error during linting: {e}")
        return False

def main():
    """
    Main function to orchestrate the configuration mutation and testing process.
    """
    parser = setup_argparse()
    args = parser.parse_args()

    try:
        # Load the configuration file
        config = load_config(args.config_file)

        # Mutate the configuration
        mutated_config = mutate_config(config, args.mutation_rate)

        # Determine the output file
        output_file = args.output_file if args.output_file else args.config_file

        # Save the mutated configuration to the output file
        save_config(mutated_config, output_file)

        # Optionally lint the mutated config
        if args.lint:
            if not lint_config(output_file):
                logging.error("Linting failed.  Aborting test.")
                return 1

        # Optionally run a test command
        if args.test_command:
            return_code = run_test_command(output_file, args.test_command)
            if return_code != 0:
                logging.error("Test command failed.")
                return 1
            else:
                logging.info("Test command passed.")
                return 0

        logging.info("Configuration mutated successfully.")
        return 0  # Success

    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")
        return 1  # Error
    except ValueError as e:
        logging.error(f"Value error: {e}")
        return 1 # Error
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return 1 # Error


if __name__ == "__main__":
    exit(main())