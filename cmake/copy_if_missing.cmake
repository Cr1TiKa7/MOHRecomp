# cmake -DSRC=<file> -DDST=<file> -P copy_if_missing.cmake
# Copies SRC to DST only when DST does not exist yet, so a build never
# overwrites a file the player owns (keybinds.ini is edited in the launcher).
if(NOT EXISTS "${DST}")
    file(COPY_FILE "${SRC}" "${DST}")
endif()
