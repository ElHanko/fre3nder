# SPDX-License-Identifier: GPL-2.0-only
# Derived from Linux arch/mips/boot/zcompressed/Makefile in the Ingenic SDK.

targets := xImage vmlinuz vmlinux.bin vmlinux.bin.gz head.o misc.o piggy.o dummy.o

OBJS := $(obj)/head.o $(obj)/misc.o

ifeq ($(strip $(LOADADDR)),)
$(error LOADADDR is required)
endif
ifeq ($(strip $(KERNEL_ENTRY)),)
$(error KERNEL_ENTRY is required)
endif
ifeq ($(strip $(XIMAGE_LOADADDR)),)
$(error XIMAGE_LOADADDR is required)
endif

LD_ARGS := -m elf32ltsmip -T $(srctree)/$(src)/ld.script \
	-Ttext $(XIMAGE_LOADADDR) -Bstatic -EL
OBJCOPY_ARGS := -O elf32-tradlittlemips

KBUILD_CFLAGS := $(shell echo $(KBUILD_CFLAGS) | sed -e "s/-pg//")
KBUILD_CFLAGS := $(filter-out -fstack-protector -fno-stack-check \
	-fstack-protector-strong,$(KBUILD_CFLAGS))
KBUILD_CFLAGS := $(KBUILD_CFLAGS) -D__KERNEL__

drop-sections := .reginfo .mdebug .comment .note .pdr .options .MIPS.options
strip-flags := $(addprefix --remove-section=,$(drop-sections))

$(obj)/vmlinux.bin: $(VMLINUX)
	$(OBJCOPY) -O binary $(strip-flags) $(VMLINUX) $@

$(obj)/vmlinux.bin.gz: $(obj)/vmlinux.bin
	gzip -n -9 -c $< > $@

$(obj)/head.o: $(srctree)/$(src)/head.S $(obj)/vmlinux.bin.gz
	$(CC) $(KBUILD_AFLAGS) $(a_flags) \
		-DIMAGESIZE=$(shell stat -c '%s' $(obj)/vmlinux.bin.gz) \
		-DKERNEL_ENTRY=$(KERNEL_ENTRY) \
		-DLOADADDR=$(LOADADDR) \
		-c -o $@ $<

$(obj)/vmlinuz: $(OBJS) $(srctree)/$(src)/ld.script \
	$(obj)/vmlinux.bin.gz $(obj)/dummy.o
	$(OBJCOPY) \
		--add-section=.image=$(obj)/vmlinux.bin.gz \
		--set-section-flags=.image=contents,alloc,load,readonly,data \
		$(obj)/dummy.o $(obj)/piggy.o
	$(LD) $(LD_ARGS) -o $@ $(OBJS) $(obj)/piggy.o
	$(OBJCOPY) $(OBJCOPY_ARGS) $@ $@ \
		-R .comment -R .stab -R .stabstr -R .initrd -R .sysmap

$(obj)/xImage: $(obj)/vmlinuz
	$(OBJCOPY) -O binary $< $(obj)/zImage
	mkimage -A mips -O linux -T kernel -C none \
		-a $(XIMAGE_LOADADDR) -e $(XIMAGE_LOADADDR) \
		-n 'Linux-$(KERNELRELEASE)' \
		-d $(obj)/zImage $@

xImage: $(obj)/xImage
