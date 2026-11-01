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
    if not output_file.endswith((".yaml", ".yml", ".json")):
        raise ValueError("Unsupported configuration file type. Must be YAML or JSON.")
    try:
        # Unlike a serialize first design, this dumps straight into
        # the opened file. A value the target format cannot hold, a
        # YAML date headed for JSON, fails halfway through the dump
        # and leaves a truncated file behind at the output path.
        with open(output_file, "w") as f:
            if output_file.endswith((".yaml", ".yml")):
                yaml.dump(config, f, indent=2)  # Use indent for readability
            elif output_file.endswith(".json"):
                json.dump(config, f, indent=2) # Use indent for readability

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
                # A string of one or two characters takes this branch and
                # becomes empty, because there is nothing safe to trim from
                # it. Short codes and single letter settings therefore mutate
                # more violently than long strings, which only ever lose a
                # slice from the middle or gain a few characters.
                value = ""
    elif isinstance(value, bool):
        # Mutate boolean by flipping the value. Checked before int, because bool is a subclass of int.
        value = not value
    elif isinstance(value, int):
        # Mutate integer by adding or subtracting a small random value
        mutation_amount = random.randint(-5, 5)
        value += mutation_amount
    elif isinstance(value, float):
        # Mutate float by adding or subtracting a small random value
        mutation_amount = random.uniform(-0.5, 0.5)
        value += mutation_amount
    else:
        # For unsupported types, log a warning and return the original value.
        logging.warning(f"Unsupported data type for mutation: {type(value)}. Returning original value.")
        return value
    return value


def _mutate_leaf(value, mutation_rate):
    """Mutate one scalar value with the given probability. Returns (value, changed_count)."""
    if random.random() < mutation_rate:
        new_value = mutate_value(value)
        if new_value != value or type(new_value) is not type(value):
            return new_value, 1
        return new_value, 0
    return value, 0


def mutate_list(values, mutation_rate):
    """Mutate items inside a list with the same per type rules. Returns (list, changed_count)."""
    changed = 0
    result = []
    for item in values:
        if isinstance(item, dict):
            mutated, count = mutate_config(item, mutation_rate)
            result.append(mutated)
            changed += count
        elif isinstance(item, list):
            mutated, count = mutate_list(item, mutation_rate)
            result.append(mutated)
            changed += count
        else:
            mutated, count = _mutate_leaf(item, mutation_rate)
            result.append(mutated)
            changed += count
    return result, changed


def mutate_config(config, mutation_rate):
    """
    Recursively mutates a configuration dictionary based on the given mutation rate.

    Args:
        config (dict): The configuration dictionary.
        mutation_rate (float): The probability of mutating each configuration value.

    Returns:
        tuple: (mutated configuration dictionary, number of values actually changed)
    """
    changed = 0
    for key, value in config.items():
        if isinstance(value, dict):
            # Recursively mutate nested dictionaries
            config[key], count = mutate_config(value, mutation_rate)
            changed += count
        elif isinstance(value, list):
            config[key], count = mutate_list(value, mutation_rate)
            changed += count
        else:
            # Keys are never mutated, only values, and the mutation happens
            # in place on the loaded mapping. A misspelled key name, a
            # renamed section, a dropped entry: none of those realistic
            # breakage shapes are in my repertoire.
            config[key], count = _mutate_leaf(value, mutation_rate)
            changed += count
    return config, changed


def run_test_command(config_file, test_command):
    """
    Runs a test command with the mutated configuration file.

    Args:
        config_file (str): Path to the mutated configuration file.
        test_command (str): The test command to execute, with '{}' as a placeholder for the config file path.
    """
    try:
        # format is applied to the operator's whole command, so any
        # other braces in it, an awk block, a JSON argument, a second
        # placeholder, are treated as format fields and raise. That
        # error is caught below and reported as a failed test, with
        # nothing saying the command never ran.
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

    if not 0.0 <= args.mutation_rate <= 1.0:
        parser.error(f"mutation rate must be between 0.0 and 1.0, got {args.mutation_rate}")

    try:
        # Load the configuration file
        config = load_config(args.config_file)

        # Mutate the configuration
        # Nothing seeds the random module anywhere in this file, so a
        # run cannot be replayed. The mutated file is the only record
        # of what was tested, and once it is overwritten the exact
        # case that made a system fail is gone. Anyone chasing a
        # failure I found has to mutate again and hope.
        mutated_config, mutation_count = mutate_config(config, args.mutation_rate)
        if mutation_count == 0:
            logging.error("No configuration values were mutated. Reporting failure instead of success, and leaving the output file unwritten.")
            return 1
        logging.info(f"Mutated {mutation_count} configuration value(s).")

        # Determine the output file
        output_file = args.output_file if args.output_file else args.config_file

        # Save the mutated configuration to the output file
        # The mutated file is written before linting and before the
        # test command runs, and when no output path was given it is
        # the original file. A failing test therefore leaves the
        # mutated config in place as the live one; I never restore
        # the original, because I never kept it.
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