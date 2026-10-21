# Native NEXTSTEP AppKit with the shared RAM framebuffer renderer.
CFLAGS += -Ifrontends/openstep -Ifrontends/framebuffer
CFLAGS += -DNETSURF_OPENSTEP_USE_FRAMEBUFFER -Dnsframebuffer -DFB_USE_FREETYPE
CFLAGS += '-DNETSURF_FB_RESPATH="$(NETSURF_FB_RESPATH)"'
CFLAGS += '-DNETSURF_FB_FONTPATH="$(NETSURF_FB_FONTPATH)"'
CFLAGS += '-DNETSURF_FB_FONT_SANS_SERIF="$(NETSURF_FB_FONT_SANS_SERIF)"'
CFLAGS += '-DNETSURF_FB_FONT_SANS_SERIF_BOLD="$(NETSURF_FB_FONT_SANS_SERIF_BOLD)"'
CFLAGS += '-DNETSURF_FB_FONT_SANS_SERIF_ITALIC="$(NETSURF_FB_FONT_SANS_SERIF_ITALIC)"'
CFLAGS += '-DNETSURF_FB_FONT_SANS_SERIF_ITALIC_BOLD="$(NETSURF_FB_FONT_SANS_SERIF_ITALIC_BOLD)"'
CFLAGS += '-DNETSURF_FB_FONT_SERIF="$(NETSURF_FB_FONT_SERIF)"'
CFLAGS += '-DNETSURF_FB_FONT_SERIF_BOLD="$(NETSURF_FB_FONT_SERIF_BOLD)"'
CFLAGS += '-DNETSURF_FB_FONT_SERIF_ITALIC="$(NETSURF_FB_FONT_SERIF_ITALIC)"'
CFLAGS += '-DNETSURF_FB_FONT_SERIF_ITALIC_BOLD="$(NETSURF_FB_FONT_SERIF_ITALIC_BOLD)"'
CFLAGS += '-DNETSURF_FB_FONT_MONOSPACE="$(NETSURF_FB_FONT_MONOSPACE)"'
CFLAGS += '-DNETSURF_FB_FONT_MONOSPACE_BOLD="$(NETSURF_FB_FONT_MONOSPACE_BOLD)"'
CFLAGS += '-DNETSURF_FB_FONT_MONOSPACE_ITALIC="$(NETSURF_FB_FONT_MONOSPACE_ITALIC)"'
CFLAGS += '-DNETSURF_FB_FONT_MONOSPACE_ITALIC_BOLD="$(NETSURF_FB_FONT_MONOSPACE_ITALIC_BOLD)"'
CFLAGS += '-DNETSURF_FB_FONT_CURSIVE="$(NETSURF_FB_FONT_CURSIVE)"'
CFLAGS += '-DNETSURF_FB_FONT_FANTASY="$(NETSURF_FB_FONT_FANTASY)"'
CFLAGS += $(shell $(PKG_CONFIG) --cflags libnsfb freetype2)
# The RAM surface is registered by a constructor in its own archive member.
# Retain that member even though only its constructor refers to its data.
LDFLAGS += -Wl,-u,_ram_rtns
LDFLAGS += $(shell $(PKG_CONFIG) --libs libnsfb freetype2)
# NEXTSTEP math routines live in libsys_s, selected by the compiler driver.
LDFLAGS += $(NEXTSTEP_APPKIT) $(NEXTSTEP_FOUNDATION)
LDFLAGS += -Wl,-sectcreate,__ICON,__header,frontends/openstep/res/NetSurf.iconheader
LDFLAGS += -Wl,-segprot,__ICON,r,r -Wl,-sectcreate,__ICON,app,frontends/openstep/res/NetSurf.tiff
OBJCFLAGS := $(CFLAGS) -fconstant-string-class=NXConstantString
OBJC_WARNFLAGS :=
S_FRONTEND := main.m BrowserWindowController.m PlotView.m schedule.m clipboard.m smoke.m text.m \
	../openstep/FrameBufferRenderer.m ../openstep/tables/window.m ../openstep/tables/fetch.m \
	../framebuffer/framebuffer.c ../framebuffer/bitmap.c ../framebuffer/findfile.c \
	../framebuffer/font_freetype.c
SOURCES = $(S_COMMON) $(S_IMAGE) $(S_BROWSER) $(S_FRONTEND)
content/fetchers/about/about.c: testament
EXETARGET := NetSurf
