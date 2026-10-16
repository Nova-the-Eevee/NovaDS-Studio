# NovaDS Studio v0.5.1 - real Lua build works without Python inside MSYS2
# Based on the standard devkitPro nds-examples ARM9 template.
.SUFFIXES:
ifeq ($(strip $(DEVKITARM)),)
$(error DEVKITARM isn't set: run this in devkitPro MSYS2, or set DEVKITPRO and DEVKITARM)
endif

include $(DEVKITARM)/ds_rules

TARGET := NovaDS_Game
BUILD := build
SOURCES := source lua
INCLUDES := source lua
# The real Lua source is prepared by setup_lua.py before recursive make.
LUA_CFILES := lapi.c lcode.c lctype.c ldebug.c ldo.c ldump.c lfunc.c lgc.c llex.c lmem.c lobject.c lopcodes.c lparser.c lstate.c lstring.c ltable.c ltm.c lundump.c lvm.c lzio.c lauxlib.c lbaselib.c lcorolib.c lmathlib.c lstrlib.c ltablib.c lutf8lib.c
LUA_REQUIRED := lua/lapi.c lua/lcode.c lua/lctype.c lua/ldebug.c lua/ldo.c lua/ldump.c lua/lfunc.c lua/lgc.c lua/llex.c lua/lmem.c lua/lobject.c lua/lopcodes.c lua/lparser.c lua/lstate.c lua/lstring.c lua/ltable.c lua/ltm.c lua/lundump.c lua/lvm.c lua/lzio.c lua/lauxlib.c lua/lbaselib.c lua/lcorolib.c lua/lmathlib.c lua/lstrlib.c lua/ltablib.c lua/lutf8lib.c lua/lua.h lua/lauxlib.h lua/lualib.h lua/luaconf.h lua/lua.hpp lua/lapi.h lua/lcode.h lua/lctype.h lua/ldebug.h lua/ldo.h lua/lfunc.h lua/lgc.h lua/ljumptab.h lua/llex.h lua/llimits.h lua/lmem.h lua/lobject.h lua/lopcodes.h lua/lopnames.h lua/lparser.h lua/lprefix.h lua/lstate.h lua/lstring.h lua/ltable.h lua/ltm.h lua/lundump.h lua/lvm.h lua/lzio.h

ARCH := -march=armv5te -mtune=arm946e-s
CFLAGS := -g -Wall -Wextra -O2 -ffunction-sections -fdata-sections $(ARCH) $(INCLUDE) -DARM9
CXXFLAGS := $(CFLAGS) -fno-rtti -fno-exceptions
ASFLAGS := -g $(ARCH)
LDFLAGS := -specs=ds_arm9.specs -g $(ARCH) -Wl,-Map,$(notdir $*.map)
LIBS := -lnds9 -lm
LIBDIRS := $(LIBNDS)

ifneq ($(BUILD),$(notdir $(CURDIR)))
export OUTPUT := $(CURDIR)/$(TARGET)
export VPATH := $(foreach dir,$(SOURCES),$(CURDIR)/$(dir))
export DEPSDIR := $(CURDIR)/$(BUILD)
CFILES := $(foreach dir,$(filter-out lua,$(SOURCES)),$(notdir $(wildcard $(dir)/*.c))) $(LUA_CFILES)
CPPFILES := $(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.cpp)))
SFILES := $(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.s)))
export LD := $(if $(strip $(CPPFILES)),$(CXX),$(CC))
export OFILES := $(CPPFILES:.cpp=.o) $(CFILES:.c=.o) $(SFILES:.s=.o)
export INCLUDE := $(foreach dir,$(INCLUDES),-I$(CURDIR)/$(dir)) $(foreach dir,$(LIBDIRS),-I$(dir)/include) -I$(CURDIR)/$(BUILD)
export LIBPATHS := $(foreach dir,$(LIBDIRS),-L$(dir)/lib)
# The first explicit target must be the ROM build, not lua-prep.
# Without this, plain `make` only prepares Lua, then silently stops.
.DEFAULT_GOAL := all
.PHONY: all $(BUILD) clean lua-prep
all: $(BUILD)
lua-prep:
	@missing=; for file in $(LUA_REQUIRED); do \
		if [ ! -f "$$file" ]; then missing="$$file"; break; fi; \
	done; \
	if [ -z "$$missing" ]; then \
		echo "Lua 5.4.9 sources present; Python not needed in MSYS2."; \
	elif command -v python3 >/dev/null 2>&1; then \
		python3 setup_lua.py; \
	elif command -v python >/dev/null 2>&1; then \
		python setup_lua.py; \
	else \
		echo "ERROR: Lua sources are missing ($$missing) and this shell has no Python." >&2; \
		echo "Run 'py -3 setup_lua.py' in Windows PowerShell in this exported folder," >&2; \
		echo "or click Build ROM inside NovaDS Studio v0.5.1." >&2; \
		exit 127; \
	fi
$(BUILD): lua-prep
	@mkdir -p $@
	@$(MAKE) --no-print-directory -C $(BUILD) -f $(CURDIR)/Makefile
clean:
	@rm -rf $(BUILD) $(TARGET).elf $(TARGET).nds
else
# Recursive build runs here from the build/ directory.
.DEFAULT_GOAL := all
.PHONY: all
all: $(OUTPUT).nds
$(OUTPUT).nds: $(OUTPUT).elf
$(OUTPUT).elf: $(OFILES)
-include $(DEPSDIR)/*.d
endif
