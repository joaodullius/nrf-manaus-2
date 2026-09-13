# Signal centering pipeline

Gestures can be continuous (e.g. running, swimming, etc.) and non-continuous, which have a start and finish (e.g. swipe left, swipe right, jump, etc.).

## Applicable for non-continuous gestures

Non-continuous gestures require additional data preparation step: segmentation of raw data into perfect samples with gesture signal peak being in the middle of the feature extraction window. A user must (subjectively) decide what is the timeframe of the longest gesture (e.g. 1 second), then given the sampling rate (e.g. 100Hz) this will be the window for all gestures segmentation in the raw data in order to create perfect training samples.
 
## Code

Data processing function `segment_data_around_peaks.main` applies to separate files: can be used on a file which consists of multiple samples of raw data of one non-continuous gesture.

The only required argument is the `TRAINING_WINDOW_SIZE` - constant in the code, which corresponds to the desired window size inside which the signal will be centered.

Additional arguments:
`gesture` - for correct processed file naming.
`nrows_to_remove` - idle data at the beginning and end of dataframe to remove.

Find the usage example below in `segment_data_around_peaks`