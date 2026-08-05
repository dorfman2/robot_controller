import depthai as dai

devs = dai.Device.getAllAvailableDevices()
print("num devices:", len(devs))
if devs:
    d = devs[0]
    print("DeviceInfo attrs:", [a for a in dir(d) if not a.startswith("_")])
    print(
        "  name:", getattr(d, "name", None), "deviceId:", getattr(d, "deviceId", None)
    )
print("Camera methods:", [m for m in dir(dai.node.Camera) if not m.startswith("_")])
print("--- Camera.build doc ---")
print((dai.node.Camera.build.__doc__ or "")[:600])
print("--- Camera.requestOutput doc ---")
print((dai.node.Camera.requestOutput.__doc__ or "")[:800])
