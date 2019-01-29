
import threading
import pprint

from custom_components.aarlo.pyaarlo.device import ArloChildDevice
from custom_components.aarlo.pyaarlo.util import ( http_get )
from custom_components.aarlo.pyaarlo.constant import( BRIGHTNESS_KEY,
                                CAPTURED_TODAY_KEY,
                                FLIP_KEY,
                                LAST_CAPTURE_KEY,
                                LAST_IMAGE_DATA_KEY,
                                LAST_IMAGE_KEY,
                                MEDIA_COUNT_KEY,
                                MEDIA_UPLOAD_KEYS,
                                MIRROR_KEY,
                                MOTION_SENS_KEY,
                                PRELOAD_DAYS )

class ArloCamera(ArloChildDevice):

    def __init__( self,name,arlo,attrs ):
        super().__init__( name,arlo,attrs )
        self._cache_count = None
        self._cached_videos = None
        self._min_days_vdo_cache = PRELOAD_DAYS
        self._lock = threading.Lock()
        self._arlo._bg.run_in( self._update_media,10 )

    # media library finished. Update our counts
    def _update_media( self ):
        self._arlo.info('reloading cache for ' + self._name)
        count,videos = self._arlo._ml.videos_for( self )
        if videos:
            captured_today = len([video for video in videos if video.created_today])
            last_captured = videos[0].created_at_pretty('%Y-%m-%d %H:%M:%S')
        else:
            captured_today = 0
            last_captured = None

        # update local copies
        with self._lock:
            self._cache_count = count
            self._cached_videos = videos

        # signal up!
        self._save_and_do_callbacks( CAPTURED_TODAY_KEY,captured_today )
        self._save_and_do_callbacks( LAST_CAPTURE_KEY,last_captured )
        self._do_callbacks( 'mediaUploadNotification',True )

    def _update_last_image( self ):
        self._arlo.info('getting image for ' + self.name )
        img = None
        url = self._arlo._st.get( [self.device_id,LAST_IMAGE_KEY],None )
        if url is not None:
            img = http_get( url )
        if img is None:
            self._arlo.debug('using blank image for ' + self.name )
            img = self._arlo.blank_image

        # signal up if nedeed
        self._save_and_do_callbacks( LAST_IMAGE_DATA_KEY,img )

    def _event_handler( self,resource,event ):
        self._arlo.info( self.name + ' CAMERA got one ' + resource )

        # stream has stopped or recording has stopped
        if resource == 'mediaUploadNotification':

            # look for all possible keys
            for key in MEDIA_UPLOAD_KEYS:
                value = event.get(key,None)
                if value is not None:
                    self._save_and_do_callbacks( key,value )

            # catch this one, update URL if passed in notification
            if LAST_IMAGE_KEY in event:
                self._arlo.debug( self.name + ' thumbnail changed' )
                self.update_last_image()

            # recording stopped then reload library
            if event.get('recordingStopped',False) == True:
                self._arlo.debug( 'recording stopped, updating library' )
                self._arlo._ml.queue_load( self._update_media )

            return

        # pass on to lower layer
        super()._event_handler( resource,event )

    @property
    def last_image(self):
        return self._arlo._st.get( [self._device_id,LAST_IMAGE_KEY],None )

    # fill this out...
    @property
    def last_image_from_cache(self):
        return self._arlo._st.get( [self._device_id,LAST_IMAGE_DATA_KEY],self._arlo.blank_image )

    @property
    def last_video(self):
        with self._lock:
            if self._cached_videos:
                return self._cached_videos[0]
        return None

    @property
    def last_capture(self):
        return self._arlo._st.get( [self._device_id,LAST_CAPTURE_KEY],None )

    @property
    def brightness(self):
        return self._arlo._st.get( [self._device_id,BRIGHTNESS_KEY],None )

    @property
    def flip_state(self):
        return self._arlo._st.get( [self._device_id,FLIP_KEY],None )

    @property
    def mirror_state(self):
        return self._arlo._st.get( [self._device_id,MIRROR_KEY],None )

    @property
    def motion_detection_sensitivity(self):
        return self._arlo._st.get( [self._device_id,MOTION_SENS_KEY],None )

    @property
    def powersave_mode(self):
        return 'optimized'

    @property
    def unseen_videos(self):
        return self._arlo._st.get( [self._device_id,MEDIA_COUNT_KEY],0 )

    @property
    def captured_today(self):
        return self._arlo._st.get( [self._device_id,CAPTURED_TODAY_KEY],0 )

    @property
    def min_days_vdo_cache(self):
        return self._min_days_vdo_cache

    @min_days_vdo_cache.setter
    def min_days_vdo_cache(self, value):
        self._min_days_vdo_cache = value

    def update_media( self ):
        self._arlo.info( 'queing media update' )
        self._arlo._bg.run_low( self._update_media )

    def update_last_image( self ):
        self._arlo.info( 'queing image update' )
        self._arlo._bg.run_low( self._update_last_image )

    def has_capability( self,cap ):
        if cap in ( 'last_capture','captured_today','battery_level','signal_strength' ):
            return True
        if cap in ( 'audio','audioDetected','sound' ) and self.model_id.startswith('VMC4030'):
            return True
        return super().has_capability( cap )

