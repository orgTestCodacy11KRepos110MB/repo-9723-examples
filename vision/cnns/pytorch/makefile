all: install get-data install-turbojpeg

install-turbojpeg: get-turbojpeg build-turbojpeg

install:
	pip3 install -r requirements.txt
	pip3 uninstall pillow -y
	CC="cc -mavx2" pip3 install --no-cache-dir -U --force-reinstall pillow-simd
	HOROVOD_WITH_PYTORCH=1 pip3 install --no-cache-dir 'horovod==0.24.3'

get-turbojpeg:
	cd datasets && rm -rf libjpeg-turbo && git clone https://github.com/libjpeg-turbo/libjpeg-turbo.git
	cd datasets/libjpeg-turbo && git checkout 0565548 && git apply ../turbojpeg.diff

build-turbojpeg:
	cd datasets/libjpeg-turbo && mkdir -p build
	cd datasets/libjpeg-turbo/build && export CMAKE_PREFIX_PATH="$(shell pwd)/datasets/turbojpeg" && cmake -DCMAKE_INSTALL_PREFIX:PATH="$$CMAKE_PREFIX_PATH" -DCFLAGS="-march=native -O3" ..
	cd datasets/libjpeg-turbo/build && make -j 96 && make install

get-data:
	cd datasets && ./get_images.sh

test:
	cd tests && python3 -m pytest -n 10 --forked
	cd tests_serial && python3 -m pytest
