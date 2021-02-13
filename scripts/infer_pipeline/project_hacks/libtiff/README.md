##### `configure: error: cannot guess build type; you must specify one`

* This is because `config/config.guess` cannot get the build type

* copy `my_config.guess` to the root of the cloned `libtiff` folder. If this error occurs, the configure script will do the following to replace the `config/config.guess`
  ```shell
  mv config/config.guess config/config.guess.old
  mv my_config.guess config/config.guess
  ```
 
