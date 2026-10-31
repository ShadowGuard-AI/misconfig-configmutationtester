![Banner](banner.png)

# misconfig-ConfigMutationTester
Randomly mutates configuration values within defined boundaries to assess the system's resilience to unexpected input and identify potential vulnerabilities or unexpected behavior due to configuration errors. - Focused on Check for misconfigurations in configuration files or infrastructure definitions

## Install
`git clone https://github.com/ShadowGuardAI/misconfig-configmutationtester`

## Usage
`python3 main.py config.yaml [-m 0.1] [-o output.yaml] [-t 'test command {}'] [--lint]`

## Parameters
- `config_file`: Path to the configuration file (YAML or JSON, positional, required). Runs use fixture copies; without -o the original file is overwritten, as documented for -o.
- `-h`: Show help message and exit
- `-m`, `--mutation_rate`: The probability (0.0 to 1.0) of mutating each configuration value. Default: 0.1. Rates outside 0.0 to 1.0 are rejected at exit 2. Values inside lists are mutated with the same rules as mapping values, and boolean values are flipped, not converted to integers. A run that mutates no value exits 1 and does not write an output file.
- `-o`: Path to save the mutated configuration file. If not provided, overwrites the original file. The output extension (.yaml, .yml, or .json) is checked before the file is opened, so an unsupported target is refused without being truncated.
- `-t`: Command to execute with the mutated configuration. Example: 'my_app --config {}'
- `--lint`: Run yamllint/jsonlint on the mutated config file before testing. The yamllint and jsonlint executables are external prerequisites for this option and must be installed and on the PATH; they are not Python requirements.

## License
Copyright (c) ShadowGuardAI
