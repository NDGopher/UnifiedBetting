// Enhanced notification system with different sounds and detailed alerts
class EnhancedNotifier {
  private highSound: HTMLAudioElement;
  private mediumSound: HTMLAudioElement;
  private lowSound: HTMLAudioElement;

  constructor() {
    // Create audio elements for different EV levels with error handling
    try {
      this.highSound = new Audio('/sounds/high-alert.mp3');
      this.mediumSound = new Audio('/sounds/medium-alert.mp3');
      this.lowSound = new Audio('/sounds/low-alert.mp3');
    } catch (error) {
      console.warn('Could not initialize audio elements:', error);
      // Create dummy audio elements to prevent errors
      this.highSound = new Audio();
      this.mediumSound = new Audio();
      this.lowSound = new Audio();
    }
    
    // Request notification permission on initialization
    this.requestNotificationPermission();
  }

  async requestNotificationPermission() {
    if ('Notification' in window) {
      const permission = await Notification.requestPermission();
      console.log('Notification permission:', permission);
    }
  }

  playSound(ev: number) {
    try {
      let audioToPlay: HTMLAudioElement | null = null;
      
      if (ev > 10) {
        audioToPlay = this.highSound;
      } else if (ev > 5) {
        audioToPlay = this.mediumSound;
      } else if (ev > 2.5) {
        audioToPlay = this.lowSound;
      }
      
      if (audioToPlay && audioToPlay.src) {
        // Check if audio is ready to play
        if (audioToPlay.readyState >= 2) { // HAVE_CURRENT_DATA
          audioToPlay.play().catch(error => {
            console.warn('Could not play sound:', error);
          });
        } else {
          // Audio not loaded, try to load it
          audioToPlay.load();
          audioToPlay.play().catch(error => {
            console.warn('Could not play sound after loading:', error);
          });
        }
      }
    } catch (error) {
      console.warn('Could not play sound:', error);
    }
  }

  showNotification(alert: any) {
    if (Notification.permission !== 'granted') {
      return;
    }

    const ev = alert.ev || 0;
    let title = '';
    let icon = '';

    if (ev > 10) {
      title = '🚨 HIGH EV ALERT!';
      icon = '/icons/high-ev.png';
    } else if (ev > 5) {
      title = '⚡ Good EV Alert';
      icon = '/icons/medium-ev.png';
    } else if (ev > 2.5) {
      title = '📊 EV Alert';
      icon = '/icons/low-ev.png';
    } else {
      return; // Don't notify for low EV
    }

    // Play appropriate sound
    this.playSound(ev);

    // Create detailed notification
    const bodyLines = [
      alert.matchup || 'Unknown Matchup',
      alert.league || '',
      `${alert.betLabel || 'N/A'} | ${alert.odds || 'N/A'} vs NVP ${alert.nvp || 'N/A'}`,
      `EV: ${ev.toFixed(2)}%`,
    ].filter(Boolean);
    const notification = new Notification(title, {
      body: bodyLines.join('\n'),
      icon: icon,
      requireInteraction: true, // Stays until clicked
      tag: alert.eventId, // Groups similar alerts
      badge: '/icons/badge.png'
    });

    // Auto-close after 30 seconds if not clicked
    setTimeout(() => {
      notification.close();
    }, 30000);
  }
}

// Create singleton instance
export const notifier = new EnhancedNotifier();

// Export function for easy use
export const showEnhancedNotification = (alert: any) => {
  notifier.showNotification(alert);
}; 