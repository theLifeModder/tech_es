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

import { fs } from 'node:fs';
import { process } from 'node:process';
import { path } from 'node:path';
import { execSync } from 'node:child_process';
import { dir } from 'node:console';

function setTargetParentPath(){
 
    const args = process.argv.slice(2);
    const targetParentPath = ""
    const stats = fs.statSync(args[0])

    if (args.length === 0){

        targetParentPath = process.cwd();

    } else if(fs.existsSync(args[0])){

        targetParentPath = path.resolve(args[0]);

    } else if(typeof(args[0])==='string' && args[0]!==''){

        const parsed = path.parse(args[0]);
        if(parsed.root || parsed.dir || parsed.base){

            try{

                fs.mkdirSync(args[0], { recursive: true });
                targetParentPath = path.resolve(args[0]);

            }catch(error){

                if (error.code === 'EACCES') {
                    console.error('Error: Permission denied to create directories. Installing packages at ');
                } else if (error.code === 'ENOTDIR') {
                    console.error('Error: A parent path segment is an existing file, not a folder.');
                } else {
                    console.error('An unexpected error occurred:', error.message);
                }            
                targetParentPath = process.cwd();

            }
        }
    }
    return targetParentPath;
}

async function runCommand(cmd, quiet = 'false', timeout = 300) {

    if(quiet !== 'true' && quiet !== 'false') {

        timeoutMs = timeout * 1000

        try {

            // Execution pauses here until the shell command finishes
            const { stdout, stderr } = await execPromise(cmd, { timeout: timeoutMs });   
            return stdout.trim();

        } catch (error) {

            console.error(`Command failed:\n\n${error.message}`);

            if (quiet === 'true'){

                console.error(`\n\nContinuing Execution.\n`);
                
            } else {

                console.error(`\n\nStopping Execution.\n`);
                throw error;
            }
            
        }
    }
}

function install_teches_fs() {

    const targetParentPath = setTargetParentPath();

    console.log("Checking environment and installing teches_fs cli tool...");
    
    const modules = fs.readdirSync(targetParentPath, { withFileTypes: true })
    .filter(dirent => dirent.isDirectory())
    .map(dirent => dirent.name);

    for(module of modules){

        if(dir.startsWith("teches_")) {

            const installPath = targetParentPath + path.sep + module
            // Attempt standard pip installation strategies
            const commands = [
                `pip install -e ${installPath}`,
                `python3 -m pip install -e ${installPath}`,
                `python -m pip install -e ${installPath}`
            ];

            for (const cmd of commands) {

                try {

                    // Run the install and forward output so you can see packaging errors
                    execSync(cmd, { stdio: 'inherit' });
                    console.log(`Success! ${teches_fs} installed completely.`);
                    return;

                } catch (e) {   

                    console.error(`\nCritical Error: Failed to execute pip install.`);
                    console.error(`\n${dir} could not be installed.`);
                    console.error(`\nPlease verify that your Python paths are configured and your pyproject.toml is valid.\n`);
                    console.error(`error thrown because of the following:\n\n${e}\n\n`);
                }
            }
        }       
    }    
}

run();
