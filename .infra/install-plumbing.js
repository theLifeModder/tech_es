// const { execSync } = require('child_process');

// function run() {
//     console.log("Checking environment and installing teches_fs cli tool...");
//     const targetPath = "./.infra/teches_fs";

//     // Array of python/pip command variants to try sequentially
//     const commands = [
//         `pip install -e ${targetPath}`,
//         `python3 -m pip install -e ${targetPath}`,
//         `python -m pip install -e ${targetPath}`,
//         // Fallback bootstrap sequences if pip went missing
//         `python3 -m ensurepip --default-pip && python3 -m pip install -e ${targetPath}`,
//         `python -m ensurepip --default-pip && python -m pip install -e ${targetPath}`
//     ];

//     for (const cmd of commands) {
//         try {
//             // Ignore stderr warnings from Windows App store aliases
//             execSync(cmd, { stdio: ['ignore', 'inherit', 'ignore'] });
//             console.log("Success! teches_fs installed completely.");
//             return;
//         } catch (e) {
//             // Silently fall through to the next command variant
//         }
//     }

//     // If all commands fail, the user genuinely lacks a valid Python installation
//     console.log("\n[Notice] Python environment could not be automatically located.");
//     console.log("Attempting automatic silent download & installation for Windows...");
    
//     try {
//         // Download and execute the official silent network installer tool for Python
//         execSync(`powershell -Command "Invoke-WebRequest -Uri 'https://python.org' -OutFile 'py_installer.exe'; Start-Process 'py_installer.exe' -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1' -Wait; Remove-Item 'py_installer.exe'"`, { stdio: 'inherit' });
        
//         // Final link pass once system variable paths refresh
//         execSync(`pip install -e ${targetPath}`, { stdio: 'inherit' });
//         console.log("Success! Python and teches_fs are fully operational.");
//     } catch (err) {
//         console.error("Critical: Automatic installer failed. Please download Python manually from python.org.");
//         process.exit(1);
//     }
// }

// run();

const { execSync } = require('child_process');

function run() {
    console.log("Checking environment and installing teches_fs cli tool...");
    const targetPath = "./teches_fs";

    // Attempt standard pip installation strategies
    const commands = [
        `pip install -e ${targetPath}`,
        `python3 -m pip install -e ${targetPath}`,
        `python -m pip install -e ${targetPath}`
    ];

    for (const cmd of commands) {
        try {
            // Run the install and forward output so you can see packaging errors
            execSync(cmd, { stdio: 'inherit' });
            console.log("Success! teches_fs installed completely.");
            return;
        } catch (e) {
            // Keep looping to try other python aliases
        }
    }

    console.error("\nCritical Error: Failed to execute pip install.");
    console.error("Please verify that your Python paths are configured and your pyproject.toml is valid.");
    process.exit(1);
}

run();
