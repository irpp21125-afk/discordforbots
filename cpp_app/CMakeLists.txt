cmake_minimum_required(VERSION 3.16)
project(support_bot_panel VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Поиск MySQL C API
# Windows: обычно C:/Program Files/MySQL/MySQL Server 8.0
# Linux:   apt install libmysqlclient-dev

if(WIN32)
    set(MYSQL_ROOT "C:/Program Files/MySQL/MySQL Server 8.0")
    if(NOT EXISTS "${MYSQL_ROOT}/include/mysql.h")
        message(FATAL_ERROR
            "MySQL C API не найден по пути ${MYSQL_ROOT}.\n"
            "Укажите путь: cmake -DMYSQL_ROOT=C:/path/to/mysql .")
    endif()
    include_directories("${MYSQL_ROOT}/include")
    link_directories("${MYSQL_ROOT}/lib")
else()
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(MYSQL REQUIRED mysqlclient)
    include_directories(${MYSQL_INCLUDE_DIRS})
endif()

add_executable(support_bot_panel src/main.cpp)

if(WIN32)
    target_link_libraries(support_bot_panel libmysql)
    # копируем DLL рядом с exe после сборки
    add_custom_command(TARGET support_bot_panel POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${MYSQL_ROOT}/lib/libmysql.dll"
            $<TARGET_FILE_DIR:support_bot_panel>
    )
else()
    target_link_libraries(support_bot_panel ${MYSQL_LIBRARIES})
endif()
