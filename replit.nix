{pkgs}: {
  deps = [
    pkgs.chromium
    pkgs.gtk3
    pkgs.xorg.libxcb
    pkgs.xorg.libXrandr
    pkgs.xorg.libXfixes
    pkgs.xorg.libXext
    pkgs.xorg.libXdamage
    pkgs.xorg.libXcomposite
    pkgs.xorg.libX11
    pkgs.at-spi2-core
    pkgs.at-spi2-atk
    pkgs.alsa-lib
    pkgs.pango
    pkgs.mesa
    pkgs.libxkbcommon
    pkgs.libdrm
    pkgs.dbus
    pkgs.cups
    pkgs.atk
    pkgs.glib
    pkgs.expat
    pkgs.nss
    pkgs.nspr
  ];
}
