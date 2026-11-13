// Camera - g3x - platform_camera.h
// Supported by Canon PowerShot G3 X GM1.10C reverse engineering

#ifndef PLATFORM_CAMERA_H
#define PLATFORM_CAMERA_H

    #define PLATFORM                            "g3x"
    #define PLATFORMSUB                         "110c"

    #define CAM_PROPSET                         10

    #define CAM_HAS_NATIVE_ND_FILTER            1   // Camera has built-in ND filter with Canon menu support
    #define CAM_HAS_ND_FILTER                   1   // Camera has built-in ND filter

    #undef  CAM_KEY_PRESS_DELAY
    #define CAM_KEY_PRESS_DELAY                 60  // delay after a press

    #define CAM_ADJUSTABLE_ALT_BUTTON           1
    #define CAM_ALT_BUTTON_NAMES                { "WiFi", "Video", "Display", "Playback" }
    #define CAM_ALT_BUTTON_OPTIONS              { KEY_WIFI, KEY_VIDEO, KEY_DISPLAY, KEY_PLAYBACK }

    #define CAM_DRYOS                           1
    #define CAM_DRYOS_2_3_R39                   1
    #define CAM_DRYOS_2_3_R47                   1

    #define CAM_HAS_CMOS                        1

    #undef  CAM_CHDK_HAS_EXT_VIDEO_MENU
    #undef  CAM_VIDEO_CONTROL

    #define CAM_SIMPLE_MOVIE_STATUS             1
    #define CAM_IS_VID_REC_WORKS                1

    #define CAM_SWIVEL_SCREEN                   1
    #define CAM_HAS_VIDEO_BUTTON                1

    #undef  CAM_UNCACHED_BIT
    #define CAM_UNCACHED_BIT                    0x40000000

    // 8.8 - 220.0 mm (24 - 600 mm equivalent, f/2.8 - 5.6)
    #define CAM_DNG_LENS_INFO                   { 88,10, 2200,10, 28,10, 56,10 }
    #define cam_CFAPattern                      0x02010100

    #define CAM_RAW_ROWPIX                      5632
    #define CAM_RAW_ROWS                        3710

    #define CAM_JPEG_WIDTH                      5472
    #define CAM_JPEG_HEIGHT                     3648

    #define CAM_ACTIVE_AREA_X1                  96
    #define CAM_ACTIVE_AREA_Y1                  18
    #define CAM_ACTIVE_AREA_X2                  5632
    #define CAM_ACTIVE_AREA_Y2                  3710

    #undef  CAM_SENSOR_BITS_PER_PIXEL
    #define CAM_SENSOR_BITS_PER_PIXEL           14

    #undef  CAM_BLACK_LEVEL
    #define CAM_BLACK_LEVEL                     2047

    #define PARAM_CAMERA_NAME                   3
    #define CAM_DATE_FOLDER_NAMING              0x80
    #define CAM_FILE_COUNTER_IS_VAR             1

    #define DRAW_ON_ACTIVE_BITMAP_BUFFER_ONLY   1
    #define CAM_DETECT_BITMAP_UPDATE            1

    #undef  CAM_BITMAP_WIDTH
    #undef  CAM_BITMAP_HEIGHT
    #undef  CAM_SCREEN_WIDTH
    #undef  CAM_SCREEN_HEIGHT

    #define CAM_BITMAP_WIDTH                    736
    #define CAM_BITMAP_HEIGHT                   480
    #define CAM_SCREEN_WIDTH                    720
    #define CAM_SCREEN_HEIGHT                   480

    #define MKDIR_RETURN_ONE_ON_SUCCESS         1

    #undef  CAM_CIRCLE_OF_CONFUSION
    #define CAM_CIRCLE_OF_CONFUSION             11

    #define cam_CalibrationIlluminant1          17
    #define cam_CalibrationIlluminant2          21

    #define CAM_COLORMATRIX1 \
    11125, 10000, -5937, 10000,  355, 10000, \
    -2979, 10000, 10926, 10000, 2360, 10000, \
     -116, 10000,   835, 10000, 6064, 10000

    #define CAM_COLORMATRIX2 \
     9602, 10000, -3823, 10000, -937, 10000, \
    -2984, 10000, 11495, 10000, 1675, 10000, \
     -407, 10000,  1415, 10000, 5049, 10000

    #define CAM_FORWARDMATRIX1 \
     4264, 10000, 4193, 10000, 1187, 10000, \
     1832, 10000, 7811, 10000,  357, 10000, \
      854, 10000,   16, 10000, 7381, 10000

    #define CAM_FORWARDMATRIX2 \
     4518, 10000, 3965, 10000, 1161, 10000, \
     1832, 10000, 7811, 10000,  357, 10000, \
      854, 10000,   16, 10000, 7381, 10000

    #define CAM_NEED_SET_ZOOM_DELAY             300

    #define CAM_USE_ALT_SET_ZOOM_POINT          1
    #define CAM_USE_ALT_PT_MoveOpticalZoomAt    1

#endif
