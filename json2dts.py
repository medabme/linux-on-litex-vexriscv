#!/usr/bin/env python3

import sys
import json
import argparse

parser = argparse.ArgumentParser(description="LiteX's CSR JSON to Linux DTS generator")
parser.add_argument("csr_json", help="CSR JSON file")
args = parser.parse_args()

d = json.load(open(args.csr_json))

kB = 1024
mB = kB*1024

aliases = {}

# Header -------------------------------------------------------------------------------------------

dts = """
/dts-v1/;

/ {
	#address-cells = <0x2>;
	#size-cells = <0x2>;
	compatible = "enjoy-digital,litex-vexriscv-soclinux";
	model = "VexRiscv SoCLinux";
"""

# Boot Arguments -----------------------------------------------------------------------------------

dts += """
	chosen {{
		bootargs = "mem={main_ram_size_mb}M@0x{main_ram_base:x} rootwait console=liteuart earlycon=sbi root=/dev/ram0 init=/sbin/init swiotlb=32";
		linux,initrd-start = <0x{linux_initrd_start:x}>;
		linux,initrd-end   = <0x{linux_initrd_end:x}>;
	}};
""".format(
		main_ram_base=d["memories"]["main_ram"]["base"],
		main_ram_size=d["memories"]["main_ram"]["size"],
		main_ram_size_mb=d["memories"]["main_ram"]["size"]//mB,

		linux_initrd_start=d["memories"]["main_ram"]["base"] + 8*mB,
		linux_initrd_end=d["memories"]["main_ram"]["base"] + 16*mB)

# CPU ----------------------------------------------------------------------------------------------

dts += """
	cpus {{
		#address-cells = <0x1>;
		#size-cells = <0x0>;
		timebase-frequency = <{sys_clk_freq}>;

		cpu@0 {{
			clock-frequency = <0x0>;
			compatible = "spinalhdl,vexriscv", "sifive,rocket0", "riscv";
			d-cache-block-size = <0x40>;
			d-cache-sets = <0x40>;
			d-cache-size = <0x8000>;
			d-tlb-sets = <0x1>;
			d-tlb-size = <0x20>;
			device_type = "cpu";
			i-cache-block-size = <0x40>;
			i-cache-sets = <0x40>;
			i-cache-size = <0x8000>;
			i-tlb-sets = <0x1>;
			i-tlb-size = <0x20>;
			mmu-type = "riscv,sv32";
			reg = <0x0>;
			riscv,isa = "rv32ima";
			sifive,itim = <0x1>;
			status = "okay";
			tlb-split;
		}};
	}};
""".format(sys_clk_freq=int(50e6) if "sim" in d["constants"] else d["constants"]["config_clock_frequency"])

# Memory -------------------------------------------------------------------------------------------

dts += """
	memory@{main_ram_base:x} {{
		device_type = "memory";
		reg = <0x0 0x{main_ram_base:x} 0x1 0x{main_ram_size:x}>;
	}};
""".format(main_ram_base=d["memories"]["main_ram"]["base"],
		   main_ram_size=d["memories"]["main_ram"]["size"])

# SoC ----------------------------------------------------------------------------------------------

dts += """
	soc {
		#address-cells = <0x2>;
		#size-cells = <0x2>;
		compatible = "simple-bus";
		ranges;
"""

# Interrupt controller

dts += """
		intc0: interrupt-controller {
			interrupt-controller;
			#interrupt-cells = <1>;
			compatible = "vexriscv,intc0";
			status = "okay";
		};
"""

	# SoC Controller -----------------------------------------------------------------------------------

dts += """
		soc_ctrl0: soc_controller@{soc_ctrl_csr_base:x} {{
			compatible = "litex,soc_controller";
			reg = <0x0 0x{soc_ctrl_csr_base:x} 0x0 0xc>;
			status = "okay";
		}};
	""".format(soc_ctrl_csr_base=d["csr_bases"]["ctrl"])

	# UART -----------------------------------------------------------------------------------------

if "uart" in d["csr_bases"]:
	aliases["serial0"] = "liteuart0"
	dts += """
		liteuart0: serial@{uart_csr_base:x} {{
			device_type = "serial";
			compatible = "litex,liteuart";
			reg = <0x0 0x{uart_csr_base:x} 0x0 0x100>;
			status = "okay";
		}};
	""".format(uart_csr_base=d["csr_bases"]["uart"])

	# Ethernet MAC ---------------------------------------------------------------------------------
if "ethphy" in d["csr_bases"] and "ethmac" not in d["csr_bases"]:
		pass

if "ethphy" in d["csr_bases"] and "ethmac" in d["csr_bases"]:
	dts += """
		mac0: mac@{ethmac_csr_base:x} {{
			compatible = "litex,liteeth";
			reg = <0x0 0x{ethmac_csr_base:x} 0x0 0x7c
				0x0 0x{ethphy_csr_base:x} 0x0 0x0a
				0x0 0x{ethmac_mem_base:x} 0x0 0x2000>;
			tx-fifo-depth = <{ethmac_tx_slots}>;
			rx-fifo-depth = <{ethmac_rx_slots}>;
		}};
	""".format(ethphy_csr_base=d["csr_bases"]["ethphy"],
			   ethmac_csr_base=d["csr_bases"]["ethmac"],
			   ethmac_mem_base=d["memories"]["ethmac"]["base"],
			   ethmac_tx_slots=d["constants"]["ethmac_tx_slots"],
			   ethmac_rx_slots=d["constants"]["ethmac_rx_slots"])

	# Leds -----------------------------------------------------------------------------------------

if "leds" in d["csr_bases"]:
	dts += """
		leds: gpio@{leds_csr_base:x} {{
			compatible = "litex,gpio";
			reg = <0x0 0x{leds_csr_base:x} 0x0 0x4>;
			litex,direction = "out";
			status = "disabled";
		}};
	""".format(leds_csr_base=d["csr_bases"]["leds"])

	# RGB Led --------------------------------------------------------------------------------------

for name in ["rgb_led_r0", "rgb_led_g0", "rgb_led_b0"]:
	if name in d["csr_bases"]:
		dts += """
		{pwm_name}: pwm@{pwm_csr_base:x} {{
			compatible = "litex,pwm";
			reg = <0x0 0x{pwm_csr_base:x} 0x0 0x24>;
			clock = <100000000>;
			#pwm-cells = <3>;
			status = "okay";
		}};
	""".format(pwm_name=name,
			   pwm_csr_base=d["csr_bases"][name])

	# Switches -------------------------------------------------------------------------------------

if "switches" in d["csr_bases"]:
	dts += """
		switches: gpio@{switches_csr_base:x} {{
			compatible = "litex,gpio";
			reg = <0x0 0x{switches_csr_base:x} 0x0 0x4>;
			litex,direction = "in";
			status = "disabled";
		}};
	""".format(switches_csr_base=d["csr_bases"]["switches"])

	# SPI ------------------------------------------------------------------------------------------

if "spi" in d["csr_bases"]:
	aliases["spi0"] = "litespi0"

	dts += """
		litespi0: spi@{spi_csr_base:x} {{
			compatible = "litex,litespi";
			reg = <0x0 0x{spi_csr_base:x} 0x0 0x100>;
			status = "okay";

			litespi,max-bpw = <8>;
			litespi,sck-frequency = <1000000>;
			litespi,num-cs = <1>;

			#address-cells = <0x1>;
			#size-cells = <0x1>;

			spidev0: spidev@0 {{
			compatible = "linux,spidev";
			reg = <0 0>;
			spi-max-frequency = <1000000>;
			status = "okay";
			}};
		}};
	""".format(spi_csr_base=d["csr_bases"]["spi"])

	# SPIFLASH ---------------------------------------------------------------------------------------

if "spiflash" in d["csr_bases"]:
	aliases["spiflash"] = "litespiflash"

	dts += """
		litespiflash: spiflash@{spiflash_csr_base:x} {{
			compatible = "litex,spiflash";
			reg = <0x0 0x{spiflash_csr_base:x} 0x0 0x100>;
			status = "okay";
			flash: flash@0 {{
				compatible = "jedec,spi-nor";
				reg = <0x0 0x0 0x0 0x{spiflash_size:x}>;
			}};
		}};
	""".format(spiflash_csr_base=d["csr_bases"]["spiflash"], spiflash_size=d["memories"]["spiflash"]["size"])

	# SPISDCARD ------------------------------------------------------------------------------------

if False: # FIXME: Disable it for now.
#if "spisdcard" in d["csr_bases"]:
	aliases["sdcard0"] = "litespisdcard0"

	dts += """
		litespisdcard0: spi@{spisdcard_csr_base:x} {{
			compatible = "litex,litespi";
			reg = <0x0 0x{spisdcard_csr_base:x} 0x0 0x100>;
			status = "okay";

			litespi,max-bpw = <8>;
			litespi,sck-frequency = <1000000>;
			litespi,num-cs = <1>;

			mmc-slot@0 {{
				compatible = "mmc-spi-slot";
				reg = <0 0>;
				voltage-ranges = <3300 3300>;
				spi-max-frequency = <1000000>;
			}};
		}};
	""".format(spisdcard_csr_base=d["csr_bases"]["spisdcard"])

	# I2C ------------------------------------------------------------------------------------------

if "i2c0" in d["csr_bases"]:
	dts += """
		i2c0: i2c@{i2c0_csr_base:x} {{
			compatible = "litex,i2c";
			reg = <0x0 0x{i2c0_csr_base:x} 0x0 0x5>;
			status = "okay";
		}};
""".format(i2c0_csr_base=d["csr_bases"]["i2c0"])

	# XADC -----------------------------------------------------------------------------------------

if "xadc" in d["csr_bases"]:
	dts += """
		hwmon0: xadc@{xadc_csr_base:x} {{
			compatible = "litex,hwmon-xadc";
			reg = <0x0 0x{xadc_csr_base:x} 0x0 0x20>;
			status = "okay";
		}};
""".format(xadc_csr_base=d["csr_bases"]["xadc"])

	# Framebuffer ----------------------------------------------------------------------------------

if "framebuffer" in d["csr_bases"]:
	# FIXME: dynamic framebuffer base and size
	framebuffer_base   = 0xc8000000
	framebuffer_width  = d["constants"]["litevideo_h_active"]
	framebuffer_height = d["constants"]["litevideo_v_active"]
	dts += """
		framebuffer0: framebuffer@f0000000 {{
			compatible = "simple-framebuffer";
			reg = <0x0 0x{framebuffer_base:x} 0x0 0x{framebuffer_size:x}>;
			width = <{framebuffer_width}>;
			height = <{framebuffer_height}>;
			stride = <{framebuffer_stride}>;
			format = "a8b8g8r8";
		}};
	""".format(framebuffer_base=framebuffer_base,
			   framebuffer_width=framebuffer_width,
			   framebuffer_height=framebuffer_height,
			   framebuffer_size=framebuffer_width*framebuffer_height*4,
			   framebuffer_stride=framebuffer_width*4)

	dma_offset = framebuffer_base - d["memories"]["main_ram"]["base"]
	dts += """
		litevideo0: gpu@{litevideo_base:x} {{
			compatible = "litex,litevideo";
			reg = <0x0 0x{litevideo_base:x} 0x0 0x100>;
			litevideo,pixel-clock = <{litevideo_pixel_clock}>;
			litevideo,h-active = <{litevideo_h_active}>;
			litevideo,h-blanking = <{litevideo_h_blanking}>;
			litevideo,h-sync = <{litevideo_h_sync}>;
			litevideo,h-front-porch = <{litevideo_h_front_porch}>;
			litevideo,v-active = <{litevideo_v_active}>;
			litevideo,v-blanking = <{litevideo_v_blanking}>;
			litevideo,v-sync = <{litevideo_v_sync}>;
			litevideo,v-front-porch = <{litevideo_v_front_porch}>;
			litevideo,dma-offset = <0x{litevideo_dma_offset:x}>;
			litevideo,dma-length = <0x{litevideo_dma_length:x}>;
		}};
	""".format(litevideo_base=d["csr_bases"]["framebuffer"],
			   litevideo_pixel_clock=int(d["constants"]["litevideo_pix_clk"] / 1e3),
			   litevideo_h_active=d["constants"]["litevideo_h_active"],
			   litevideo_h_blanking=d["constants"]["litevideo_h_blanking"],
			   litevideo_h_sync=d["constants"]["litevideo_h_sync"],
			   litevideo_h_front_porch=d["constants"]["litevideo_h_front_porch"],
			   litevideo_v_active=d["constants"]["litevideo_v_active"],
			   litevideo_v_blanking=d["constants"]["litevideo_v_blanking"],
			   litevideo_v_sync=d["constants"]["litevideo_v_sync"],
			   litevideo_v_front_porch=d["constants"]["litevideo_v_front_porch"],
			   litevideo_dma_offset=dma_offset,
			   litevideo_dma_length=4*framebuffer_width*framebuffer_height)

	#·ICAPBitstream --------------------------------------------------------------------------------

if "icap_bit" in d["csr_bases"]:
	dts += """
		fpga0: icap@{icap_csr_base:x} {{
			compatible = "litex,fpga-icap";
			reg = <0x0 0x{icap_csr_base:x} 0x0 0x14>;
			status = "okay";
		}};
""".format(icap_csr_base=d["csr_bases"]["icap_bit"])

	# CLK ----------------------------------------------------------------------------------

def add_clkout(clkout_nr, clk_f, clk_p, clk_dn, clk_dd):

	return """	CLKOUT{clkout_nr}: CLKOUT{clkout_nr} {{
				compatible = "litex,clk";
				#clock-cells =	<0>;
				clock-output-names = "CLKOUT{clkout_nr}";
				reg = <{clkout_nr}>;
				litex,clock-frequency = <{clk_f}>;
				litex,clock-phase = <{clk_p}>;
				litex,clock-duty-num = <{clk_dn}>;
				litex,clock-duty-den = <{clk_dd}>;
			}};
		""".format(clkout_nr=clkout_nr, clk_f=clk_f, clk_p=clk_p, clk_dn=clk_dn, clk_dd=clk_dd)

if "mmcm" in d["csr_bases"]:
	clkout_def_freq = d["constants"]["clkout_def_freq"]
	clkout_def_phase = d["constants"]["clkout_def_phase"]
	clkout_def_duty_num = d["constants"]["clkout_def_duty_num"]
	clkout_def_duty_den = d["constants"]["clkout_def_duty_den"]
	mmcm_lock_timeout = d["constants"]["mmcm_lock_timeout"]
	mmcm_drdy_timeout = d["constants"]["mmcm_drdy_timeout"]
	sys_clk = d["constants"]["config_clock_frequency"]

	dts += """
		clk0: clk@{mmcm_csr_base:x} {{
			compatible = "litex,clk";
			reg = <0x0 0x{mmcm_csr_base:x} 0x0 0x100>;
			#clock-cells = <1>;
			#address-cells = <1>;
			#size-cells = <0>;
			clock-output-names = "CLKOUT0",
						 "CLKOUT1",
						 "CLKOUT2",
						 "CLKOUT3",
						 "CLKOUT4",
						 "CLKOUT5",
						 "CLKOUT6";
			litex,nclkout = <7>;
			litex,lock-timeout = <{mmcm_lock_timeout}>;
			litex,drdy-timeout = <{mmcm_drdy_timeout}>;
			litex,sys-clock-frequency = <{sys_clk}>;
		""".format(mmcm_csr_base = d["csr_bases"]["mmcm"],
			   mmcm_lock_timeout = mmcm_lock_timeout,
			   mmcm_drdy_timeout = mmcm_drdy_timeout,
			   sys_clk = sys_clk)
	for clkout_nr in range(7):
		dts += add_clkout(clkout_nr, clkout_def_freq, clkout_def_phase,
								clkout_def_duty_num,
								clkout_def_duty_den)
	dts += """
		};"""
dts += """
	};"""

# Aliases -----------------------------------------------------------------------------------------

if aliases:
	dts += """
	aliases {
"""
	for alias in aliases:
		dts += """
	   {} = &{};
""".format(alias, aliases[alias])
	dts += """
	};
"""

dts += """
};
"""

# --------------------------------------------------------------------------------------------------

if "leds" in d["csr_bases"]:
	dts += """
&leds {
	litex,ngpio = <4>;
	status = "okay";
};
	"""

if "switches" in d["csr_bases"]:
	dts += """
&switches {
	litex,ngpio = <4>;
	status = "okay";
};
	"""

print(dts)
