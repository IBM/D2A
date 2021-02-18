#!/bin/bash
 
function make_clean {
  echo ""
  echo "------------------------"
  echo "make clean"
  echo "------------------------"
  time make clean
  }

export ZHENGYU_PREFIX="/u/zhengyu/local_x86"
echo "configure_project: ZHENGYU_PREFIX=$ZHENGYU_PREFIX"
export PATH="$ZHENGYU_PREFIX/bin:$PATH"
export LD_LIBRARY_PATH="$ZHENGYU_PREFIX/lib:$ZHENGYU_PREFIX/lib64:$LD_LIBRARY_PATH"

if [[ $PROJECT == "openssl" ]];  then
  CONFIG_CMD="./config -v"
elif [[ $PROJECT == "ffmpeg" ]]; then
  CONFIG_CMD="./configure --disable-doc"
elif [[ $PROJECT == "qemu" ]];   then
  # qemu requires python 3.5+
  export PATH="$ZHENGYU_PREFIX/bin:/home/amorari/anaconda3/bin:/usr/local/bin:/usr/bin" 
  CONFIG_CMD="../configure"
elif [[ $PROJECT == "httpd" ]];  then
  ./buildconf
  CONFIG_CMD="./configure --disable-ssl --disable-setenvif"
elif [[ $PROJECT == "nginx" ]];  then
  CONFIG_CMD="auto/configure"
elif [[ $PROJECT == "libtiff" ]];  then
  if [[ -f "autogen.sh" ]]; then
    ./autogen.sh
    CONFIG_CMD="./configure"
  else
    CONFIG_CMD="./configure --noninteractive"
  fi
elif [[ $PROJECT == "libav" ]];  then
  CONFIG_CMD="./configure --disable-altivec --disable-protocol=rtmp --disable-protocol=rtmpt"
elif [[ $PROJECT == "binutils" ]];  then
  CONFIG_CMD="./configure --disable-werror"
else
  CONFIG_CMD=""
fi

#Allow customization for non-R92 environments
if [ -f $pipeline_path/customize_configure.sh ]; then
  source $pipeline_path/customize_configure.sh
  echo configuration customized from: $pipeline_path/customize_configure.sh
fi

export CC=""
export CXX=""
export CFLAGS=""
export CXXFLAGS=""
export LD=""

echo ""
echo "----------------------------------------"
echo "Project configured as:"
echo "PATH = $PATH"
echo "LD_LIBRARY_PATH = $LD_LIBRARY_PATH"
echo "PROJECT = $PROJECT"
echo "configure command = $CONFIG_CMD"

$CONFIG_CMD 2>&1 | tee ./config.out

# the project may provide other ways to config legacy code
if [[ $PROJECT == "openssl" ]]
then
  if [ ! "$(cat ./config.out | grep 'Configuring for linux-elf')" == "" ] || [ ! "$(cat ./config.out | grep 'Configured for linux-generic32')" == "" ] 
  then
    echo "Configuring legacy code"
    ./Configure cc
  fi
  make_clean
elif [[ $PROJECT == "ffmpeg" ]]
then
  if [ ! "$(cat ./config.out | grep 'Unknown option \"--disable-doc\"')" == "" ]
  then
    echo "-----------------------"
    echo "Configuring legacy code"
    ./configure
  elif [ ! "$(cat ./config.out | grep 'WARNING: unknown architecture ppc64le')" == "" ]
  then
    echo "-----------------------"
    echo "Configuring legacy code"
    ./configure --disable-doc
  fi
  make_clean
elif [[ $PROJECT == "libtiff" ]]
then
  if [ ! "$(cat ./config.out | grep 'cannot guess build type;')" == "" ]
  then
    mv config/config.guess config/config.guess.old
    cp my_config.guess config/config.guess
    ./configure
  fi
fi



