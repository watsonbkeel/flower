def main():
    from flower_pi.actuators.pump import GPIOPump
    pump = GPIOPump()
    pump.off()


if __name__ == "__main__":
    main()
