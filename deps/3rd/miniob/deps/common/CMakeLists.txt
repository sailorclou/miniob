MESSAGE(STATUS "This is PROJECT_BINARY_DIR dir " ${PROJECT_BINARY_DIR})
MESSAGE(STATUS "This is PROJECT_SOURCE_DIR dir " ${PROJECT_SOURCE_DIR})

INCLUDE_DIRECTORIES(${CMAKE_CURRENT_SOURCE_DIR})

FILE(GLOB_RECURSE ALL_SRC  *.cpp)

#SHARED，动态库
#STATIC，静态库
ADD_LIBRARY(common STATIC ${ALL_SRC} )


IF(USE_MUSL_LIBC)
    MESSAGE(STATUS "musl libc need manually link libexecinfo")
    TARGET_LINK_LIBRARIES(common execinfo)
ENDIF(USE_MUSL_LIBC)

# 编译静态库时，自动会把同名的动态库给删除， 因此需要临时设置一下
SET_TARGET_PROPERTIES(common PROPERTIES CLEAN_DIRECT_OUTPUT 1)

SET(LIBRARY_OUTPUT_PATH ${PROJECT_BINARY_DIR}/lib)
# Target 必须在定义 ADD_EXECUTABLE 之后， programs 不受这个限制
# TARGETS和PROGRAMS 的默认权限是OWNER_EXECUTE, GROUP_EXECUTE, 和WORLD_EXECUTE，即755权限， programs 都是处理脚步类
# 类型分为RUNTIME／LIBRARY／ARCHIVE, prog
INSTALL(TARGETS common
        LIBRARY DESTINATION lib
        ARCHIVE DESTINATION lib)

# 小心 安装的时候，不要变成include/func.h, 如果这样，第二次安装的时候会变成include/func.h/func.h
# INSTALL(FILES func.h DESTINATION include/)

FILE(GLOB_RECURSE ALL_HEADER  *.h)
FOREACH(F ${ALL_HEADER})
    file(RELATIVE_PATH RELAPATH_HEADER ${PROJECT_SOURCE_DIR} ${F}) # 获取相对路径
    get_filename_component(headDir ${RELAPATH_HEADER} DIRECTORY)
    MESSAGE("Install " ${RELAPATH_HEADER} " to " ${CMAKE_INSTALL_PREFIX} "/" common "/include/" ${headDir})
    INSTALL(FILES ${RELAPATH_HEADER} DESTINATION include/${headDir})
ENDFOREACH(F)
