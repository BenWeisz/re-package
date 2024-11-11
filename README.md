# re-package 📝 📝 📝 ➡️ 📦
C project header only repackager

# Idea
I wanted to make a python script that bundles all of my C code from a project into a single header format. This is especially useful when I'm just bringing up a new project and want to have an off the shelf library thats super easy to integrate into my build system. So thats basically what this project does; it takes all your source files: heades, sources and turns them into one header file. 

# Script Usage

To use this script you need to pass it a config file as follows:

```sh
python re-package.py config.json
```

This runs ***re-package*** using the configuration in `config.json`. Below is the format for this json file:

```json
{
	"name": "cjson",
	"root": "/Users/dev/cjson",
	"source-extensions": [".c"],
	"header-extensions": [".h"],
	"patterns": [
		"+/src",
		"+/include",
		"-/src/io.c",
		"-/include/io.h"
	]
}
```

- ***name***: Denotes the project name and controls the output name of the header file. It also has an effect on how you use the output header which will be described in the next section.
- ***root***: This tells the script where the root location of the project is that you're trying to package.
- ***source-extensions***:  This denotes the file types that you want the script to consider as source type files.
- ***header-extensions***: This denotes the file types that you want the script to consider as header type files.
- ***patterns***: This is a list of patterns of files to include. They are resolved sequentially so patterns that appear later and resolved later. Each patterns is prefixed with a + or a - sign. This denotes whether files matching that pattern should be added or removed from the list of files to consider. Patterns can either be files or folders, in which case the folder is searched recursively

Looking at the above example, we first consider all files under `/src` and under `/include`. We then remove the `io.c` and `io.h` source and header since we don't want to compile that into our output files (we will refer to this as an uber file).

# Package Usage

If the script runs successfully you will see something like this:
```
Loading Files ...
Loading Progress: [13/13]
Topo-sort pass on headers: [8/8]
Creating uber file ...
Assembling code files ...
Completed: Output written to /Users/dev/cjson/cjson.h
```

The output will then be available in the `root` folder and will be named: `{name}.h`

To use this uber file in one of your projects all you need to do is create a source file which will be used to hold the implementation of the functions. You should then add this to your build system so that it gets its own translation unit.

When defining the implementation you'll want to define `{NAME}_IMPLEMENTATION` before including the uber file header. This tells the preprocessor that you also want it to include the definitions of your functions here. For my [cjson](https://github.com/BenWeisz/cjson) project, this looks as follows:

```C
... cjson.c ...

#define CJSON_IMPLEMENTATION
#include "../cjson.h"
```

After this all you have to do is include `{name}.h` where ever you need your code.

# Quirks

Right now only relative pathing is supported for `#include` directives. This means that When you're writing your code you should make your C files include your headers with relative paths to their location. For an example of this, take a look at how [cjson](https://github.com/BenWeisz/cjson) includes headers in its C files.