CMAKE_MINIMUM_REQUIRED(VERSION 3.2)
PROJECT(h2o4gpu)
INCLUDE(cmake/Utils.cmake)
LIST(APPEND CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/cmake)

SET_DEFAULT_CONFIGURATION_RELEASE()

FIND_PACKAGE(OpenMP)
FIND_PACKAGE(BLAS REQUIRED)
FIND_PACKAGE(SWIG REQUIRED)
FIND_PACKAGE(PythonLibs REQUIRED) # SWIG

# SWIG behaviour was changed 
if (${CMAKE_VERSION} VERSION_GREATER "3.13")
        cmake_policy(SET CMP0078 OLD)
endif()

INCLUDE(${SWIG_USE_FILE})

#============= OPTIONS & SETTINGS
OPTION(USE_CUDA  "Build with GPU acceleration" ON)
OPTION(DEV_BUILD  "Dev build" OFF)

# Compiler flags
SET(CMAKE_CXX_STANDARD 11)
SET(CMAKE_CXX_STANDARD_REQUIRED ON)
SET(CMAKE_POSITION_INDEPENDENT_CODE ON)
SET(CMAKE_CXX_FLAGS  "${CMAKE_CXX_FLAGS} -w")

# PythonLibs' PYTHON_INCLUDE_PATH doesn't take into account virtualenv etc.
# Open to suggestions how to do this better.
EXECUTE_PROCESS(COMMAND python -c "import numpy; print(numpy.get_include())"
        OUTPUT_VARIABLE PYTHON_INCLUDE_PATH_CUST
        OUTPUT_STRIP_TRAILING_WHITESPACE)

if(OpenMP_CXX_FOUND OR OPENMP_FOUND)
        SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${OpenMP_CXX_FLAGS}")
endif()
#============= OPTIONS & SETTINGS

# TODO probably to be removed after POGS is out in favor of XGboost GLM
ADD_DEFINITIONS(
        -D_GITHASH_=0
        -DH2O4GPU_DOUBLE
        -DH2O4GPU_SINGLE
)

#============= BUILD COMMON CPU/GPU CODE
FILE(GLOB_RECURSE COMMON_SOURCES
        src/common/*.cpp
        src/common/*.h
        src/interface_c/*.cpp
        src/interface_c/*.h
        )

INCLUDE_DIRECTORIES(
        src/include
        src/cpu/include
        # Here and not in target_include_directories b/c cmake < 3.7 which we use in Dockerfiles does not support it
        src/gpu/include
        ${PYTHON_INCLUDE_PATH}
        ${PYTHON_INCLUDE_PATH_CUST}
)

ADD_LIBRARY(commonh2o4gpu OBJECT ${COMMON_SOURCES})
#============= BUILD COMMON CPU/GPU CODE

#============= BUILD CPU LIBRARY
FILE(GLOB_RECURSE CPU_SOURCES
        src/cpu/*.cpp
        src/cpu/*.h
        )

ADD_LIBRARY(cpuh2o4gpu STATIC ${CPU_SOURCES} $<TARGET_OBJECTS:commonh2o4gpu>)
TARGET_LINK_LIBRARIES(cpuh2o4gpu ${BLAS_LIBRARIES})
#============= BUILD CPU LIBRARY

#============= SWIG
SET(CMAKE_SWIG_FLAGS -Werror)
#============= SWIG

#============= CPU SWIG
SET_SOURCE_FILES_PROPERTIES(src/swig/ch2o4gpu_cpu.i PROPERTIES CPLUSPLUS ON)

if (${CMAKE_VERSION} VERSION_LESS "3.8.0")
        SWIG_ADD_MODULE(ch2o4gpu_cpu python src/swig/ch2o4gpu_cpu.i)
else()
        SWIG_ADD_LIBRARY(ch2o4gpu_cpu LANGUAGE python SOURCES src/swig/ch2o4gpu_cpu.i)
endif()

SWIG_LINK_LIBRARIES(ch2o4gpu_cpu cpuh2o4gpu ${PYTHON_LIBRARIES})

SET_TARGET_PROPERTIES(${SWIG_MODULE_ch2o4gpu_cpu_REAL_NAME} PROPERTIES
        LINK_FLAGS ${OpenMP_CXX_FLAGS})
#============= CPU SWIG

if(USE_CUDA)
        FIND_PACKAGE(CUDA 8.0 REQUIRED)
        FIND_PACKAGE(NVML REQUIRED)

        #============= BUILD GPU LIBRARY
        ADD_DEFINITIONS(
                -DCUDA_MAJOR=${CUDA_VERSION_MAJOR}
                -DHAVECUDA
        )

        if(DEV_BUILD)
                MESSAGE(STATUS "Building DEVELOPER compute capability version.")
                SET(GPU_COMPUTE_VER 61 CACHE STRING
                        "Space separated list of compute versions to be built against")
        else()
                MESSAGE(STATUS "Building RELEASE compute capability version.")
                SET(GPU_COMPUTE_VER 35;50;52;60;61 CACHE STRING
                        "Space separated list of compute versions to be built against")
        endif()

        if(((CUDA_VERSION_MAJOR EQUAL 9) OR (CUDA_VERSION_MAJOR GREATER 9)) AND NOT DEV_BUILD)
                MESSAGE(STATUS "CUDA GREATER OR EQUAL THAN 9.0 detected, adding Volta compute capability (7.0).")
                SET(GPU_COMPUTE_VER "${GPU_COMPUTE_VER};70")
        endif()

        if(((CUDA_VERSION_MAJOR EQUAL 10) OR (CUDA_VERSION_MAJOR GREATER 10)) AND NOT DEV_BUILD)
                MESSAGE(STATUS "CUDA GREATER OR EQUAL THAN 10.0 detected, adding Turing compute capability (7.5).")
                SET(GPU_COMPUTE_VER "${GPU_COMPUTE_VER};75")
        endif()

        SET(GENCODE_FLAGS "")
        FORMAT_GENCODE_FLAGS("${GPU_COMPUTE_VER}" GENCODE_FLAGS)
        MESSAGE(STATUS "cuda architecture flags: ${GENCODE_FLAGS}")
        SET(CUDA_NVCC_FLAGS "${CUDA_NVCC_FLAGS};-Xcompiler -fPIC; -std=c++11;--expt-extended-lambda;--expt-relaxed-constexpr;${GENCODE_FLAGS};-lineinfo; -w;")

        FILE(GLOB_RECURSE GPU_SOURCES
                src/*.cu
                src/*.cuh
                src/common/*.cpp
                src/common/*.h
                )

        CUDA_ADD_LIBRARY(gpuh2o4gpu ${GPU_SOURCES} $<TARGET_OBJECTS:commonh2o4gpu> STATIC)
        SET_TARGET_PROPERTIES(gpuh2o4gpu PROPERTIES CUDA_SEPARABLE_COMPILATION ON)

        if($ENV{USENVTX})
                MESSAGE(STATUS "Building with NVTX support on.")
                SET(NVTX_LIBRARY nvToolsExt)
        endif()

        find_library(CUBLAS_STATIC_LIB NAMES libcublas_static.a 
                PATHS   "${CUDA_TOOLKIT_ROOT_DIR}/lib64" # cuda-9
                        "${CUDA_TOOLKIT_ROOT_DIR}/targets/x86_64-linux/lib/") # cuda-10
        find_library(CULIBOS_STATIC_LIB NAMES libculibos.a
                PATHS   "${CUDA_TOOLKIT_ROOT_DIR}/lib64"
                        "${CUDA_TOOLKIT_ROOT_DIR}/targets/x86_64-linux/lib/")
        find_library(CUSPARSE_STATIC_LIB NAMES libcusparse_static.a
                PATHS   "${CUDA_TOOLKIT_ROOT_DIR}/lib64"
                        "${CUDA_TOOLKIT_ROOT_DIR}/targets/x86_64-linux/lib/")
        find_library(CUSOLVER_STATIC_LIB NAMES libcusolver_static.a
                PATHS   "${CUDA_TOOLKIT_ROOT_DIR}/lib64"
                        "${CUDA_TOOLKIT_ROOT_DIR}/targets/x86_64-linux/lib/")
        

        TARGET_LINK_LIBRARIES(gpuh2o4gpu
                ${CUBLAS_STATIC_LIB}
                ${CULIBOS_STATIC_LIB}
                ${CUSOLVER_STATIC_LIB}
                ${CUSPARSE_STATIC_LIB}
                ${BLAS_LIBRARIES}
                ${NVTX_LIBRARY}
                ${NVML_LIBRARY})
        #============= BUILD GPU LIBRARY

        #============= GPU SWIG
        SET_SOURCE_FILES_PROPERTIES(src/swig/ch2o4gpu_gpu.i PROPERTIES CPLUSPLUS ON)

        if (${CMAKE_VERSION} VERSION_LESS "3.8.0")
                SWIG_ADD_MODULE(ch2o4gpu_gpu python src/swig/ch2o4gpu_gpu.i)
        else()
                SWIG_ADD_LIBRARY(ch2o4gpu_gpu LANGUAGE python SOURCES src/swig/ch2o4gpu_gpu.i)
        endif()
        SWIG_LINK_LIBRARIES(ch2o4gpu_gpu gpuh2o4gpu 
                ${PYTHON_LIBRARIES}
                ${CUBLAS_STATIC_LIB}
                ${CULIBOS_STATIC_LIB}
                ${CUSOLVER_STATIC_LIB}
                ${CUSPARSE_STATIC_LIB})

        SET_TARGET_PROPERTIES(${SWIG_MODULE_ch2o4gpu_gpu_REAL_NAME} PROPERTIES
                LINK_FLAGS ${OpenMP_CXX_FLAGS})
        #============= GPU SWIG
endif()
