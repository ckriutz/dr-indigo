# Infrastructure Deployment

## Prerequisites

Before running a dry-run or actual deployment, you must populate the `main.bicepparam` file with the required parameters. This file provides default values that can be used for all parameters defined in `main.bicep`.

Adjust the values as needed for your environment and requirements. All parameters in `main.bicep` must be provided in this file for a successful deployment.

## Deployment Instructions

### Dry-Run (What-If) Deployment

To preview the changes that will be made by your Bicep deployment without actually applying them, use the Azure CLI `what-if` operation:

```bash
az deployment sub what-if \
	--name dr-indigo-dryrun \
	--location <location> \
	--template-file main.bicep \
	--parameters main.bicepparam
```

Replace `<location>` with your Azure region (e.g., `eastus2`).

This command will show you a summary of resources that will be created, modified, or deleted.

### Actual Deployment

To perform the actual deployment, run:

```bash
az deployment sub create \
	--name dr-indigo-full \
	--location <location> \
	--template-file main.bicep \
	--parameters main.bicepparam
```

This will deploy all resources as defined in your Bicep templates and parameter files.