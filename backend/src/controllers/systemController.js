import config from '../config/config.js';
import discoveryService from '../services/discoveryService.js';

// Get current system configuration
export const getConfig = (req, res) => {
  try {
    res.json({ success: true, config: config.get() });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
};

// Update system configuration dynamically at runtime
export const updateConfig = (req, res) => {
  const { storagePath, deviceName } = req.body;

  try {
    let updated = false;

    if (deviceName && deviceName.trim()) {
      config.setDeviceName(deviceName);
      updated = true;
    }

    if (storagePath) {
      config.setStoragePath(storagePath);
      updated = true;
    }

    if (updated) {
      console.log('[System] Configuration updated dynamically.');
      // Immediately broadcast new device details to the local network
      discoveryService.broadcastPresence();
    }

    res.json({
      success: true,
      message: 'Configuration updated successfully',
      config: config.get()
    });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
};
