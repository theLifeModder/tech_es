

### ***Environment contexts:***

An environment context will be a mechanism for saving the state of an environment to recall later. We save the state as an object with properties representing key aspects of the state of the environment.

One property that every environment context will have to have is a environment context ID, with the actual property name nvctx-id in the save file. This is how we will identify the context and will be used by programs that can automatically switch to that environment.

The context environment will be saved as a json file. The name of the file will always be {env context id}.nvctx.json, where env context id is the exact value of nvctx-id in the file. Inside the file will be exactly one json object with the following properties: nvctx-id: str, creation: obj, ownership: obj, parent-id: str|none, and state: obj. A sample environment context file, named sample.nvctx.json can be found in the same folder as this document.

The environment context file is only part of the system that will be used for manipulating environment contexts. We will also need a program to create environment contexts, a program, a program to load environment contexts from a file, and a program to handle nvctx queries on the command line. There will be a command to handle all of these tasks. It will be called *** teches nvctx*** , and its basic usage will be of the form *$ teches nvctx*

### About the Command:

the synopsis for the *teches nvctx* command is as follows:

```Shell
$ teches nvctx ( (–load-from-file | –lff ) <file> | ( –save | -s )  &<location> | &(–list | -l )  &<reg-ex> | ( –query | -q ) <file-and-query> )

```

the & immediately before a phrase means that everything in the scope that follows it is optional. Lets talk about the options.
