# DepthAI Python API

DepthAI Python API can be found on Github [luxonis/depthai-python](https://github.com/luxonis/depthai-python). Below is the
reference documentation for the Python API.

### depthai

Kind: Package

#### filters

Kind: Package

Parameters for filters

##### params

Kind: Module

Parameters for filters

###### depthai.filters.params.MedianFilter

Kind: Class

Members:

  MEDIAN_OFF

  KERNEL_3x3

  KERNEL_5x5

  KERNEL_7x7

###### KERNEL_3x3: typing.ClassVar[MedianFilter]

Kind: Class Variable

###### KERNEL_5x5: typing.ClassVar[MedianFilter]

Kind: Class Variable

###### KERNEL_7x7: typing.ClassVar[MedianFilter]

Kind: Class Variable

###### MEDIAN_OFF: typing.ClassVar[MedianFilter]

Kind: Class Variable

###### __members__: typing.ClassVar[dict[str, MedianFilter]]

Kind: Class Variable

###### __eq__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __getstate__(self) -> int: int

Kind: Method

###### __hash__(self) -> int: int

Kind: Method

###### __index__(self) -> int: int

Kind: Method

###### __init__(self, value: int)

Kind: Method

###### __int__(self) -> int: int

Kind: Method

###### __ne__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __repr__(self) -> str: str

Kind: Method

###### __setstate__(self, state: int)

Kind: Method

###### __str__()

Kind: Method

###### name

Kind: Property

###### value

Kind: Property

###### depthai.filters.params.SpatialFilter

Kind: Class

###### __init__(self)

Kind: Method

###### __str__(self) -> str: str

Kind: Method

###### alpha

Kind: Property

The Alpha factor in an exponential moving average with Alpha=1 - no filter.
Alpha = 0 - infinite filter. Determines the amount of smoothing.

###### alpha.setter(self, arg0: float)

Kind: Method

###### delta

Kind: Property

Step-size boundary. Establishes the threshold used to preserve "edges". If the
disparity value between neighboring pixels exceed the disparity threshold set by
this delta parameter, then filtering will be temporarily disabled. Default value
0 means auto: 3 disparity integer levels. In case of subpixel mode it's 3*number
of subpixel levels.

###### delta.setter(self, arg0: int)

Kind: Method

###### enable

Kind: Property

Whether to enable or disable the filter.

###### enable.setter(self, arg0: bool)

Kind: Method

###### holeFillingRadius

Kind: Property

An in-place heuristic symmetric hole-filling mode applied horizontally during
the filter passes. Intended to rectify minor artefacts with minimal performance
impact. Search radius for hole filling.

###### holeFillingRadius.setter(self, arg0: int)

Kind: Method

###### numIterations

Kind: Property

Number of iterations over the image in both horizontal and vertical direction.

###### numIterations.setter(self, arg0: int)

Kind: Method

###### depthai.filters.params.SpeckleFilter

Kind: Class

###### __init__(self)

Kind: Method

###### __str__(self) -> str: str

Kind: Method

###### differenceThreshold

Kind: Property

Maximum difference between neighbor disparity pixels to put them into the same
blob. Units in disparity integer levels.

###### differenceThreshold.setter(self, arg0: int)

Kind: Method

###### enable

Kind: Property

Whether to enable or disable the filter.

###### enable.setter(self, arg0: bool)

Kind: Method

###### speckleRange

Kind: Property

Speckle search range.

###### speckleRange.setter(self, arg0: int)

Kind: Method

###### depthai.filters.params.TemporalFilter

Kind: Class

Temporal filtering with optional persistence.

###### depthai.filters.params.TemporalFilter.PersistencyMode

Kind: Class

Persistency algorithm type.

Members:

  PERSISTENCY_OFF : 

  VALID_8_OUT_OF_8 : 

  VALID_2_IN_LAST_3 : 

  VALID_2_IN_LAST_4 : 

  VALID_2_OUT_OF_8 : 

  VALID_1_IN_LAST_2 : 

  VALID_1_IN_LAST_5 : 

  VALID_1_IN_LAST_8 : 

  PERSISTENCY_INDEFINITELY : 

###### PERSISTENCY_INDEFINITELY: typing.ClassVar[TemporalFilter.PersistencyMode]

Kind: Class Variable

###### PERSISTENCY_OFF: typing.ClassVar[TemporalFilter.PersistencyMode]

Kind: Class Variable

###### VALID_1_IN_LAST_2: typing.ClassVar[TemporalFilter.PersistencyMode]

Kind: Class Variable

###### VALID_1_IN_LAST_5: typing.ClassVar[TemporalFilter.PersistencyMode]

Kind: Class Variable

###### VALID_1_IN_LAST_8: typing.ClassVar[TemporalFilter.PersistencyMode]

Kind: Class Variable

###### VALID_2_IN_LAST_3: typing.ClassVar[TemporalFilter.PersistencyMode]

Kind: Class Variable

###### VALID_2_IN_LAST_4: typing.ClassVar[TemporalFilter.PersistencyMode]

Kind: Class Variable

###### VALID_2_OUT_OF_8: typing.ClassVar[TemporalFilter.PersistencyMode]

Kind: Class Variable

###### VALID_8_OUT_OF_8: typing.ClassVar[TemporalFilter.PersistencyMode]

Kind: Class Variable

###### __members__: typing.ClassVar[dict[str, TemporalFilter.PersistencyMode]]

Kind: Class Variable

###### __eq__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __getstate__(self) -> int: int

Kind: Method

###### __hash__(self) -> int: int

Kind: Method

###### __index__(self) -> int: int

Kind: Method

###### __init__(self, value: int)

Kind: Method

###### __int__(self) -> int: int

Kind: Method

###### __ne__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __repr__(self) -> str: str

Kind: Method

###### __setstate__(self, state: int)

Kind: Method

###### __str__(self) -> str: str

Kind: Method

###### name

Kind: Property

###### value

Kind: Property

###### __init__(self)

Kind: Method

###### __str__(self) -> str: str

Kind: Method

###### alpha

Kind: Property

The Alpha factor in an exponential moving average with Alpha=1 - no filter.
Alpha = 0 - infinite filter. Determines the extent of the temporal history that
should be averaged.

###### alpha.setter(self, arg0: float)

Kind: Method

###### delta

Kind: Property

Step-size boundary. Establishes the threshold used to preserve surfaces (edges).
If the disparity value between neighboring pixels exceed the disparity threshold
set by this delta parameter, then filtering will be temporarily disabled.
Default value 0 means auto: 3 disparity integer levels. In case of subpixel mode
it's 3*number of subpixel levels.

###### delta.setter(self, arg0: int)

Kind: Method

###### enable

Kind: Property

Whether to enable or disable the filter.

###### enable.setter(self, arg0: bool)

Kind: Method

###### persistencyMode

Kind: Property

Persistency mode. If the current disparity/depth value is invalid, it will be
replaced by an older value, based on persistency mode.

###### persistencyMode.setter(self, arg0: ...)

Kind: Method

###### depthai.filters.params.ThresholdFilter

Kind: Class

Threshold filtering. Filters out distances outside of a given interval.

###### __init__(self)

Kind: Method

###### __str__(self) -> str: str

Kind: Method

###### maxRange

Kind: Property

Maximum range in depth units. Depth values over this value are invalidated.

###### maxRange.setter(self, arg0: int)

Kind: Method

###### minRange

Kind: Property

Minimum range in depth units. Depth values under this value are invalidated.

###### minRange.setter(self, arg0: int)

Kind: Method

#### modelzoo

Kind: Module

Model Zoo

##### getDefaultCachePath() -> os.PathLike: os.PathLike

Kind: Function

Get the default cache path (where models are cached)

##### getDefaultModelsPath() -> os.PathLike: os.PathLike

Kind: Function

Get the default models path (where yaml files are stored)

##### getDownloadEndpoint() -> str: str

Kind: Function

Get the download endpoint (for model querying)

##### getHealthEndpoint() -> str: str

Kind: Function

Get the health endpoint (for internet check)

##### setDefaultCachePath(path: os.PathLike)

Kind: Function

Set the default cache path (where models are cached)

Parameter ``path``:

##### setDefaultModelsPath(path: os.PathLike)

Kind: Function

Set the default models path (where yaml files are stored)

Parameter ``path``:

##### setDownloadEndpoint(endpoint: str)

Kind: Function

Set the download endpoint (for model querying)

Parameter ``endpoint``:

##### setHealthEndpoint(endpoint: str)

Kind: Function

Set the health endpoint (for internet check)

Parameter ``endpoint``:

#### nn_archive

Kind: Package

##### v1

Kind: Module

###### depthai.nn_archive.v1.Config

Kind: Class

The main class of the multi/single-stage model config scheme (multi- stage
models consists of interconnected single-stage models).

@type config_version: str @ivar config_version: String representing config
schema version in format 'x.y' where x is major version and y is minor version
@type model: Model @ivar model: A Model object representing the neural network
used in the archive.

###### __init__()

Kind: Method

###### configVersion

Kind: Property

String representing config schema version in format 'x.y' where x is major
version and y is minor version.

###### configVersion.setter(self, arg0: str | None)

Kind: Method

###### model

Kind: Property

A Model object representing the neural network used in the archive.

###### model.setter(self, arg0: Model)

Kind: Method

###### depthai.nn_archive.v1.DataType

Kind: Class

Data type of the input data (e.g., 'float32').

Represents all existing data types used in i/o streams of the model.

Precision of the model weights.

Data type of the output data (e.g., 'float32').

Members:

  BOOLEAN

  FLOAT16

  FLOAT32

  FLOAT64

  INT4

  INT8

  INT16

  INT32

  INT64

  UINT4

  UINT8

  UINT16

  UINT32

  UINT64

  STRING

###### BOOLEAN: typing.ClassVar[DataType]

Kind: Class Variable

###### FLOAT16: typing.ClassVar[DataType]

Kind: Class Variable

###### FLOAT32: typing.ClassVar[DataType]

Kind: Class Variable

###### FLOAT64: typing.ClassVar[DataType]

Kind: Class Variable

###### INT16: typing.ClassVar[DataType]

Kind: Class Variable

###### INT32: typing.ClassVar[DataType]

Kind: Class Variable

###### INT4: typing.ClassVar[DataType]

Kind: Class Variable

###### INT64: typing.ClassVar[DataType]

Kind: Class Variable

###### INT8: typing.ClassVar[DataType]

Kind: Class Variable

###### STRING: typing.ClassVar[DataType]

Kind: Class Variable

###### UINT16: typing.ClassVar[DataType]

Kind: Class Variable

###### UINT32: typing.ClassVar[DataType]

Kind: Class Variable

###### UINT4: typing.ClassVar[DataType]

Kind: Class Variable

###### UINT64: typing.ClassVar[DataType]

Kind: Class Variable

###### UINT8: typing.ClassVar[DataType]

Kind: Class Variable

###### __members__: typing.ClassVar[dict[str, DataType]]

Kind: Class Variable

###### __eq__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __getstate__(self) -> int: int

Kind: Method

###### __hash__(self) -> int: int

Kind: Method

###### __index__(self) -> int: int

Kind: Method

###### __init__(self, value: int)

Kind: Method

###### __int__(self) -> int: int

Kind: Method

###### __ne__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __repr__(self) -> str: str

Kind: Method

###### __setstate__(self, state: int)

Kind: Method

###### __str__(self) -> str: str

Kind: Method

###### name

Kind: Property

###### value

Kind: Property

###### depthai.nn_archive.v1.Head

Kind: Class

Represents head of a model.

@type name: str | None @ivar name: Optional name of the head. @type parser: str
@ivar parser: Name of the parser responsible for processing the models output.
@type outputs: List[str] | None @ivar outputs: Specify which outputs are fed
into the parser. If None, all outputs are fed. @type metadata: C{HeadMetadata} |
C{HeadObjectDetectionMetadata} | C{HeadClassificationMetadata} |
C{HeadObjectDetectionSSDMetadata} | C{HeadSegmentationMetadata} |
C{HeadYOLOMetadata} @ivar metadata: Metadata of the parser.

###### __init__(self)

Kind: Method

###### metadata

Kind: Property

Metadata of the parser.

###### metadata.setter(self, arg0: Metadata)

Kind: Method

###### name

Kind: Property

Optional name of the head.

###### name.setter(self, arg0: str | None)

Kind: Method

###### outputs

Kind: Property

Specify which outputs are fed into the parser. If None, all outputs are fed.

###### outputs.setter(self, arg0: list [ str ]| None)

Kind: Method

###### parser

Kind: Property

Name of the parser responsible for processing the models output.

###### parser.setter(self, arg0: str)

Kind: Method

###### depthai.nn_archive.v1.Input

Kind: Class

Represents input stream of a model.

@type name: str @ivar name: Name of the input layer.

@type dtype: DataType @ivar dtype: Data type of the input data (e.g.,
'float32').

@type input_type: InputType @ivar input_type: Type of input data (e.g.,
'image').

@type shape: list @ivar shape: Shape of the input data as a list of integers
(e.g. [H,W], [H,W,C], [N,H,W,C], ...).

@type layout: str @ivar layout: Lettercode interpretation of the input data
dimensions (e.g., 'NCHW').

@type preprocessing: PreprocessingBlock @ivar preprocessing: Preprocessing steps
applied to the input data.

###### __init__(self)

Kind: Method

###### dtype

Kind: Property

Data type of the input data (e.g., 'float32').

###### dtype.setter(self, arg0: DataType)

Kind: Method

###### inputType

Kind: Property

Type of input data (e.g., 'image').

###### inputType.setter(self, arg0: InputType)

Kind: Method

###### layout

Kind: Property

Lettercode interpretation of the input data dimensions (e.g., 'NCHW')

###### layout.setter(self, arg0: str | None)

Kind: Method

###### name

Kind: Property

Name of the input layer.

###### name.setter(self, arg0: str)

Kind: Method

###### preprocessing

Kind: Property

Preprocessing steps applied to the input data.

###### preprocessing.setter(self, arg0: PreprocessingBlock)

Kind: Method

###### shape

Kind: Property

Shape of the input data as a list of integers (e.g. [H,W], [H,W,C], [N,H,W,C],
...).

###### shape.setter(self, arg0: list [ int ])

Kind: Method

###### depthai.nn_archive.v1.InputType

Kind: Class

Members:

  IMAGE

  RAW

###### IMAGE: typing.ClassVar[InputType]

Kind: Class Variable

###### RAW: typing.ClassVar[InputType]

Kind: Class Variable

###### __members__: typing.ClassVar[dict[str, InputType]]

Kind: Class Variable

###### __eq__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __getstate__(self) -> int: int

Kind: Method

###### __hash__(self) -> int: int

Kind: Method

###### __index__(self) -> int: int

Kind: Method

###### __init__(self, value: int)

Kind: Method

###### __int__(self) -> int: int

Kind: Method

###### __ne__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __repr__(self) -> str: str

Kind: Method

###### __setstate__(self, state: int)

Kind: Method

###### __str__(self) -> str: str

Kind: Method

###### name

Kind: Property

###### value

Kind: Property

###### depthai.nn_archive.v1.Metadata

Kind: Class

Metadata of the parser.

Metadata for the object detection head.

@type classes: list @ivar classes: Names of object classes detected by the
model. @type n_classes: int @ivar n_classes: Number of object classes detected
by the model. @type iou_threshold: float @ivar iou_threshold: Non-max supression
threshold limiting boxes intersection. @type conf_threshold: float @ivar
conf_threshold: Confidence score threshold above which a detected object is
considered valid. @type max_det: int @ivar max_det: Maximum detections per
image. @type anchors: list @ivar anchors: Predefined bounding boxes of different
sizes and aspect ratios. The innermost lists are length 2 tuples of box sizes.
The middle lists are anchors for each output. The outmost lists go from smallest
to largest output.

Metadata for the classification head.

@type classes: list @ivar classes: Names of object classes classified by the
model. @type n_classes: int @ivar n_classes: Number of object classes classified
by the model. @type is_softmax: bool @ivar is_softmax: True, if output is
already softmaxed

Metadata for the SSD object detection head.

@type boxes_outputs: str @ivar boxes_outputs: Output name corresponding to
predicted bounding box coordinates. @type scores_outputs: str @ivar
scores_outputs: Output name corresponding to predicted bounding box confidence
scores.

Metadata for the segmentation head.

@type classes: list @ivar classes: Names of object classes segmented by the
model. @type n_classes: int @ivar n_classes: Number of object classes segmented
by the model. @type is_softmax: bool @ivar is_softmax: True, if output is
already softmaxed

Metadata for the YOLO head.

@type yolo_outputs: list @ivar yolo_outputs: A list of output names for each of
the different YOLO grid sizes. @type mask_outputs: list | None @ivar
mask_outputs: A list of output names for each mask output. @type protos_outputs:
str | None @ivar protos_outputs: Output name for the protos. @type
keypoints_outputs: list | None @ivar keypoints_outputs: A list of output names
for the keypoints. @type angles_outputs: list | None @ivar angles_outputs: A
list of output names for the angles. @type subtype: str @ivar subtype: YOLO
family decoding subtype (e.g. yolov5, yolov6, yolov7 etc.) @type n_prototypes:
int | None @ivar n_prototypes: Number of prototypes per bbox in YOLO instance
segmnetation. @type n_keypoints: int | None @ivar n_keypoints: Number of
keypoints per bbox in YOLO keypoint detection. @type is_softmax: bool | None
@ivar is_softmax: True, if output is already softmaxed in YOLO instance
segmentation

Metadata for the basic head. It allows you to specify additional fields.

@type postprocessor_path: str | None @ivar postprocessor_path: Path to the
postprocessor.

###### __init__(self)

Kind: Method

###### anchors

Kind: Property

Predefined bounding boxes of different sizes and aspect ratios. The innermost
lists are length 2 tuples of box sizes. The middle lists are anchors for each
output. The outmost lists go from smallest to largest output.

###### anchors.setter(self, arg0: list [ list [ list [ float ] ] ]| None)

Kind: Method

###### anglesOutputs

Kind: Property

A list of output names for the angles.

###### anglesOutputs.setter(self, arg0: list [ str ]| None)

Kind: Method

###### boxesOutputs

Kind: Property

Output name corresponding to predicted bounding box coordinates.

###### boxesOutputs.setter(self, arg0: str | None)

Kind: Method

###### classes

Kind: Property

Names of object classes recognized by the model.

###### classes.setter(self, arg0: list [ str ]| None)

Kind: Method

###### confThreshold

Kind: Property

Confidence score threshold above which a detected object is considered valid.

###### confThreshold.setter(self, arg0: float | None)

Kind: Method

###### extraParams

Kind: Property

Additional parameters

###### extraParams.setter(self, arg0: json)

Kind: Method

###### iouThreshold

Kind: Property

Non-max supression threshold limiting boxes intersection.

###### iouThreshold.setter(self, arg0: float | None)

Kind: Method

###### isSoftmax

Kind: Property

True, if output is already softmaxed.

True, if output is already softmaxed in YOLO instance segmentation.

###### isSoftmax.setter(self, arg0: bool | None)

Kind: Method

###### keypointsOutputs

Kind: Property

A list of output names for the keypoints.

###### keypointsOutputs.setter(self, arg0: list [ str ]| None)

Kind: Method

###### maskOutputs

Kind: Property

A list of output names for each mask output.

###### maskOutputs.setter(self, arg0: list [ str ]| None)

Kind: Method

###### maxDet

Kind: Property

Maximum detections per image.

###### maxDet.setter(self, arg0: int | None)

Kind: Method

###### nClasses

Kind: Property

Number of object classes recognized by the model.

###### nClasses.setter(self, arg0: int | None)

Kind: Method

###### nKeypoints

Kind: Property

Number of keypoints per bbox in YOLO keypoint detection.

###### nKeypoints.setter(self, arg0: int | None)

Kind: Method

###### nPrototypes

Kind: Property

Number of prototypes per bbox in YOLO instance segmnetation.

###### nPrototypes.setter(self, arg0: int | None)

Kind: Method

###### postprocessorPath

Kind: Property

Path to the postprocessor.

###### postprocessorPath.setter(self, arg0: str | None)

Kind: Method

###### protosOutputs

Kind: Property

Output name for the protos.

###### protosOutputs.setter(self, arg0: str | None)

Kind: Method

###### scoresOutputs

Kind: Property

Output name corresponding to predicted bounding box confidence scores.

###### scoresOutputs.setter(self, arg0: str | None)

Kind: Method

###### subtype

Kind: Property

YOLO family decoding subtype (e.g. yolov5, yolov6, yolov7 etc.).

###### subtype.setter(self, arg0: str | None)

Kind: Method

###### yoloOutputs

Kind: Property

A list of output names for each of the different YOLO grid sizes.

###### yoloOutputs.setter(self, arg0: list [ str ]| None)

Kind: Method

###### depthai.nn_archive.v1.MetadataClass

Kind: Class

Metadata object defining the model metadata.

Represents metadata of a model.

@type name: str @ivar name: Name of the model. @type path: str @ivar path:
Relative path to the model executable.

###### __init__(self)

Kind: Method

###### name

Kind: Property

Name of the model.

###### name.setter(self, arg0: str)

Kind: Method

###### path

Kind: Property

Relative path to the model executable.

###### path.setter(self, arg0: str)

Kind: Method

###### precision

Kind: Property

Precision of the model weights.

###### precision.setter(self, arg0: DataType | None)

Kind: Method

###### depthai.nn_archive.v1.Model

Kind: Class

A Model object representing the neural network used in the archive.

Class defining a single-stage model config scheme.

@type metadata: Metadata @ivar metadata: Metadata object defining the model
metadata. @type inputs: list @ivar inputs: List of Input objects defining the
model inputs. @type outputs: list @ivar outputs: List of Output objects defining
the model outputs. @type heads: list @ivar heads: List of Head objects defining
the model heads. If not defined, we assume a raw output.

###### __init__(self)

Kind: Method

###### heads

Kind: Property

List of Head objects defining the model heads. If not defined, we assume a raw
output.

###### heads.setter(self, arg0: list [ Head ]| None)

Kind: Method

###### inputs

Kind: Property

List of Input objects defining the model inputs.

###### inputs.setter(self, arg0: list [ Input ])

Kind: Method

###### metadata

Kind: Property

Metadata object defining the model metadata.

###### metadata.setter(self, arg0: MetadataClass)

Kind: Method

###### outputs

Kind: Property

List of Output objects defining the model outputs.

###### outputs.setter(self, arg0: list [ Output ])

Kind: Method

###### depthai.nn_archive.v1.Output

Kind: Class

Represents output stream of a model.

@type name: str @ivar name: Name of the output layer. @type dtype: DataType
@ivar dtype: Data type of the output data (e.g., 'float32').

###### __init__(self)

Kind: Method

###### dtype

Kind: Property

Data type of the output data (e.g., 'float32').

###### dtype.setter(self, arg0: DataType)

Kind: Method

###### layout

Kind: Property

List of letters describing the output layout (e.g. 'NC').

###### layout.setter(self, arg0: str | None)

Kind: Method

###### name

Kind: Property

Name of the output layer.

###### name.setter(self, arg0: str)

Kind: Method

###### shape

Kind: Property

Shape of the output as a list of integers (e.g. [1, 1000]).

###### shape.setter(self, arg0: list [ int ]| None)

Kind: Method

###### depthai.nn_archive.v1.PreprocessingBlock

Kind: Class

Preprocessing steps applied to the input data.

Represents preprocessing operations applied to the input data.

@type mean: list | None @ivar mean: Mean values in channel order. Order depends
on the order in which the model was trained on. @type scale: list | None @ivar
scale: Standardization values in channel order. Order depends on the order in
which the model was trained on. @type reverse_channels: bool | None @ivar
reverse_channels: If True input to the model is RGB else BGR. @type
interleaved_to_planar: bool | None @ivar interleaved_to_planar: If True input to
the model is interleaved (NHWC) else planar (NCHW). @type dai_type: str | None
@ivar dai_type: DepthAI input type which is read by DepthAI to automatically
setup the pipeline.

###### __init__(self)

Kind: Method

###### daiType

Kind: Property

DepthAI input type which is read by DepthAI to automatically setup the pipeline.

###### daiType.setter(self, arg0: str | None)

Kind: Method

###### interleavedToPlanar

Kind: Property

If True input to the model is interleaved (NHWC) else planar (NCHW).

###### interleavedToPlanar.setter(self, arg0: bool | None)

Kind: Method

###### mean

Kind: Property

Mean values in channel order. Order depends on the order in which the model was
trained on.

###### mean.setter(self, arg0: list [ float ]| None)

Kind: Method

###### reverseChannels

Kind: Property

If True input to the model is RGB else BGR.

###### reverseChannels.setter(self, arg0: bool | None)

Kind: Method

###### scale

Kind: Property

Standardization values in channel order. Order depends on the order in which the
model was trained on.

###### scale.setter(self, arg0: list [ float ]| None)

Kind: Method

#### node

Kind: Package

##### internal

Kind: Module

##### depthai.node.AprilTag(depthai.DeviceNode)

Kind: Class

AprilTag node.

###### getNumThreads(self) -> int: int

Kind: Method

Get number of threads to use for AprilTag detection.

Returns:
    Number of threads to use.

###### getWaitForConfigInput(self) -> bool: bool

Kind: Method

Get whether or not wait until configuration message arrives to inputConfig
Input.

###### runOnHost(self) -> bool: bool

Kind: Method

Check if the node is set to run on host

###### setNumThreads(self, numThreads: int)

Kind: Method

Set number of threads to use for AprilTag detection.

Parameter ``numThreads``:
    Number of threads to use.

###### setRunOnHost(self, arg0: bool)

Kind: Method

Specify whether to run on host or device By default, the node will run on
device.

###### setWaitForConfigInput(self, wait: bool)

Kind: Method

Specify whether or not wait until configuration message arrives to inputConfig
Input.

Parameter ``wait``:
    True to wait for configuration message, false otherwise.

###### initialConfig

Kind: Property

Initial config to use when calculating spatial location data.

###### inputConfig

Kind: Property

Input AprilTagConfig message with ability to modify parameters in runtime.
Default queue is non-blocking with size 4.

###### inputImage

Kind: Property

Input message with depth data used to retrieve spatial information about
detected object. Default queue is non-blocking with size 4.

###### out

Kind: Property

Outputs AprilTags message that carries spatial location results.

###### passthroughInputImage

Kind: Property

Passthrough message on which the calculation was performed. Suitable for when
input queue is set to non-blocking behavior.

##### depthai.node.AutoCalibration(depthai.DeviceNode)

Kind: Class

###### initialConfig: depthai.AutoCalibrationConfig

Kind: Class Variable

###### build(self, cameraLeft: Camera, cameraRight: Camera) -> AutoCalibration: AutoCalibration

Kind: Method

###### output

Kind: Property

##### depthai.node.BasaltVIO(depthai.node.ThreadedHostNode)

Kind: Class

Basalt Visual Inertial Odometry node. Performs VIO on stereo images and IMU
data.

###### runSyncOnHost(self, runOnHost: bool)

Kind: Method

###### setAccelBias(self, bias: list [ float ])

Kind: Method

###### setAccelNoiseStd(self, noise: list [ float ])

Kind: Method

###### setConfig(self, config: depthai.VioConfig)

Kind: Method

###### setConfigPath(self, path: str)

Kind: Method

###### setGyroBias(self, bias: list [ float ])

Kind: Method

###### setGyroNoiseStd(self, noise: list [ float ])

Kind: Method

###### setImuExtrinsics(self, imuExtr: depthai.TransformData)

Kind: Method

###### setImuUpdateRate(self, rate: int)

Kind: Method

###### setLocalTransform(self, transform: depthai.TransformData)

Kind: Method

###### imu

Kind: Property

Input IMU data.

###### left

Kind: Property

###### passthrough

Kind: Property

Output passthrough of left image.

###### right

Kind: Property

###### transform

Kind: Property

Output transform data.

##### depthai.node.BenchmarkIn(depthai.DeviceNode)

Kind: Class

###### logReportsAsWarnings(self, logReportsAsWarnings: bool)

Kind: Method

Log the reports as warnings

###### measureIndividualLatencies(self, attachLatencies: bool)

Kind: Method

Attach latencies to the report

###### sendReportEveryNMessages(self, num: int)

Kind: Method

Specify how many messages to measure for each report

###### setRunOnHost(self, runOnHost: bool)

Kind: Method

Specify whether to run on host or device By default, the node will run on
device.

###### input

Kind: Property

Receive messages as fast as possible

###### passthrough

Kind: Property

Passthrough for input messages (so the node can be placed between other nodes)

###### report

Kind: Property

Send a benchmark report when the set number of messages are received

##### depthai.node.BenchmarkOut(depthai.DeviceNode)

Kind: Class

###### setFps(self, fps: float)

Kind: Method

Set FPS at which the node is sending out messages. 0 means as fast as possible

###### setNumMessagesToSend(self, num: int)

Kind: Method

Sets number of messages to send, by default send messages indefinitely

Parameter ``num``:
    number of messages to send

###### setRunOnHost(self, runOnHost: bool)

Kind: Method

Specify whether to run on host or device By default, the node will run on
device.

###### input

Kind: Property

Message that will be sent repeatedly

###### out

Kind: Property

Send messages out as fast as possible

##### depthai.node.Camera(depthai.DeviceNode)

Kind: Class

###### build()

Kind: Method

###### getBoardSocket(self) -> depthai.CameraBoardSocket: depthai.CameraBoardSocket

Kind: Method

Retrieves which board socket to use

Returns:
    Board socket to use

###### getImageOrientation(self) -> depthai.CameraImageOrientation: depthai.CameraImageOrientation

Kind: Method

Get camera image orientation

Returns:
    Image orientation

###### getIspNumFramesPool(self) -> int: int

Kind: Method

Get number of frames in isp pool

Returns:
    Number of frames

###### getMaxSizePoolIsp(self) -> int: int

Kind: Method

Get maximum size of isp pool

Returns:
    Maximum size in bytes of isp pool

###### getMaxSizePoolRaw(self) -> int: int

Kind: Method

Get maximum size of raw pool

Returns:
    Maximum size in bytes of raw pool

###### getOutputsMaxSizePool(self) -> int|None: int|None

Kind: Method

Get maximum size of outputs pool for all outputs

Returns:
    Maximum size in bytes of image manip pool

###### getOutputsNumFramesPool(self) -> int|None: int|None

Kind: Method

Get number of frames in outputs pool for all outputs

Returns:
    Number of frames

###### getRawNumFramesPool(self) -> int: int

Kind: Method

Get number of frames in raw pool

Returns:
    Number of frames

###### getSensorType(self) -> depthai.CameraSensorType: depthai.CameraSensorType

Kind: Method

Get the sensor type

Returns:
    Sensor type

###### requestFullResolutionOutput(self, type: depthai.ImgFrame.Type | None = None, fps: float | None = None, useHighestResolution: bool = False) -> depthai.Node.Output: depthai.Node.Output

Kind: Method

Get a high resolution output with full FOV on the sensor. By default the
function will not use the resolutions higher than 5000x4000, as those often need
a lot of resources, making them hard to use in combination with other nodes.

Parameter ``type``:
    Type of the output (NV12, BGR, ...) - by default it's auto-selected for best
    performance

Parameter ``fps``:
    FPS of the output - by default it's auto-selected to highest possible that a
    sensor config support or 30, whichever is lower

Parameter ``useHighestResolution``:
    If true, the function will use the highest resolution available on the
    sensor, even if it's higher than 5000x4000

###### requestIspOutput(self, fps: float | None = None) -> depthai.Node.Output: depthai.Node.Output

Kind: Method

Request output with isp resolution. The fps does not vote.

###### requestOutput()

Kind: Method

###### setImageOrientation(self, imageOrientation: depthai.CameraImageOrientation) -> Camera: Camera

Kind: Method

Set camera image orientation

Parameter ``imageOrientation``:
    Image orientation to set

Returns:
    Shared pointer to the camera node

###### setIspNumFramesPool(self, num: int) -> Camera: Camera

Kind: Method

Set number of frames in isp pool (will be automatically reduced if the maximum
pool memory size is exceeded)

Parameter ``num``:
    Number of frames

Returns:
    Shared pointer to the camera node

###### setMaxSizePoolIsp(self, size: int) -> Camera: Camera

Kind: Method

Set maximum size of isp pool

Parameter ``size``:
    Maximum size in bytes of isp pool

Returns:
    Shared pointer to the camera node

###### setMaxSizePoolRaw(self, size: int) -> Camera: Camera

Kind: Method

Set maximum size of raw pool

Parameter ``size``:
    Maximum size in bytes of raw pool

Returns:
    Shared pointer to the camera node

###### setMaxSizePools(self, raw: int, isp: int, imgmanip: int) -> Camera: Camera

Kind: Method

Set maximum memory size of all pools

Parameter ``raw``:
    Maximum size in bytes of raw pool

Parameter ``isp``:
    Maximum size in bytes of isp pool

Parameter ``outputs``:
    Maximum size in bytes of outputs pools

Returns:
    Shared pointer to the camera node

###### setMockIsp(self, mockIsp: ReplayVideo) -> Camera: Camera

Kind: Method

Set mock ISP for Camera node. Automatically sets mockIsp size.

Parameter ``replay``:
    ReplayVideo node to use as mock ISP

###### setNumFramesPools(self, raw: int, isp: int, imgmanip: int) -> Camera: Camera

Kind: Method

Set number of frames in all pools (will be automatically reduced if the maximum
pool memory size is exceeded)

Parameter ``raw``:
    Number of frames in raw pool

Parameter ``isp``:
    Number of frames in isp pool

Parameter ``outputs``:
    Number of frames in outputs pools

Returns:
    Shared pointer to the camera node

###### setOutputsMaxSizePool(self, size: int) -> Camera: Camera

Kind: Method

Set maximum size of pools for all outputs

Parameter ``size``:
    Maximum size in bytes of pools for all outputs

Returns:
    Shared pointer to the camera node

###### setOutputsNumFramesPool(self, num: int) -> Camera: Camera

Kind: Method

Set number of frames in pools for all outputs

Parameter ``num``:
    Number of frames in pools for all outputs

Returns:
    Shared pointer to the camera node

###### setRawNumFramesPool(self, num: int) -> Camera: Camera

Kind: Method

Set number of frames in raw pool (will be automatically reduced if the maximum
pool memory size is exceeded)

Parameter ``num``:
    Number of frames

Returns:
    Shared pointer to the camera node

###### setSensorType(self, sensorType: depthai.CameraSensorType) -> Camera: Camera

Kind: Method

Set the sensor type to use

Parameter ``sensorType``:
    Sensor type to use

###### initialControl

Kind: Property

Initial control options to apply to sensor

###### inputControl

Kind: Property

Input for CameraControl message, which can modify camera parameters in runtime

###### mockIsp

Kind: Property

Input for mocking 'isp' functionality on RVC2. Default queue is blocking with
size 8

###### raw

Kind: Property

Outputs ImgFrame message that carries RAW10-packed (MIPI CSI-2 format) frame
data.

Captured directly from the camera sensor, and the source for the 'isp' output.

##### depthai.node.ColorCamera(depthai.DeviceNode)

Kind: Class

ColorCamera node. For use with color sensors.

###### __init__(self)

Kind: Method

###### getBoardSocket(self) -> depthai.CameraBoardSocket: depthai.CameraBoardSocket

Kind: Method

Retrieves which board socket to use

Returns:
    Board socket to use

###### getCamId(self) -> int: int

Kind: Method

###### getCamera(self) -> str: str

Kind: Method

Retrieves which camera to use by name

Returns:
    Name of the camera to use

###### getColorOrder(self) -> depthai.ColorCameraProperties.ColorOrder: depthai.ColorCameraProperties.ColorOrder

Kind: Method

Get color order of preview output frames. RGB or BGR

###### getFp16(self) -> bool: bool

Kind: Method

Get fp16 (0..255) data of preview output frames

###### getFps(self) -> float: float

Kind: Method

Get rate at which camera should produce frames

Returns:
    Rate in frames per second

###### getFrameEventFilter(self) -> list [ depthai.FrameEvent ]: list [ depthai.FrameEvent ]

Kind: Method

###### getImageOrientation(self) -> depthai.CameraImageOrientation: depthai.CameraImageOrientation

Kind: Method

Get camera image orientation

###### getInterleaved(self) -> bool: bool

Kind: Method

Get planar or interleaved data of preview output frames

###### getIspHeight(self) -> int: int

Kind: Method

Get 'isp' output height

###### getIspNumFramesPool(self) -> int: int

Kind: Method

Get number of frames in isp pool

###### getIspSize(self) -> tuple [ int, int ]: tuple [ int, int ]

Kind: Method

Get 'isp' output resolution as size, after scaling

###### getIspWidth(self) -> int: int

Kind: Method

Get 'isp' output width

###### getPreviewHeight(self) -> int: int

Kind: Method

Get preview height

###### getPreviewKeepAspectRatio(self) -> bool: bool

Kind: Method

See also:
    setPreviewKeepAspectRatio

Returns:
    Preview keep aspect ratio option

###### getPreviewNumFramesPool(self) -> int: int

Kind: Method

Get number of frames in preview pool

###### getPreviewSize(self) -> tuple [ int, int ]: tuple [ int, int ]

Kind: Method

Get preview size as tuple

###### getPreviewWidth(self) -> int: int

Kind: Method

Get preview width

###### getRawNumFramesPool(self) -> int: int

Kind: Method

Get number of frames in raw pool

###### getResolution(self) -> depthai.ColorCameraProperties.SensorResolution: depthai.ColorCameraProperties.SensorResolution

Kind: Method

Get sensor resolution

###### getResolutionHeight(self) -> int: int

Kind: Method

Get sensor resolution height

###### getResolutionSize(self) -> tuple [ int, int ]: tuple [ int, int ]

Kind: Method

Get sensor resolution as size

###### getResolutionWidth(self) -> int: int

Kind: Method

Get sensor resolution width

###### getSensorCrop(self) -> tuple [ float, float ]: tuple [ float, float ]

Kind: Method

Returns:
    Sensor top left crop coordinates

###### getSensorCropX(self) -> float: float

Kind: Method

Get sensor top left x crop coordinate

###### getSensorCropY(self) -> float: float

Kind: Method

Get sensor top left y crop coordinate

###### getStillHeight(self) -> int: int

Kind: Method

Get still height

###### getStillNumFramesPool(self) -> int: int

Kind: Method

Get number of frames in still pool

###### getStillSize(self) -> tuple [ int, int ]: tuple [ int, int ]

Kind: Method

Get still size as tuple

###### getStillWidth(self) -> int: int

Kind: Method

Get still width

###### getVideoHeight(self) -> int: int

Kind: Method

Get video height

###### getVideoNumFramesPool(self) -> int: int

Kind: Method

Get number of frames in video pool

###### getVideoSize(self) -> tuple [ int, int ]: tuple [ int, int ]

Kind: Method

Get video size as tuple

###### getVideoWidth(self) -> int: int

Kind: Method

Get video width

###### sensorCenterCrop(self)

Kind: Method

Specify sensor center crop. Resolution size / video size

###### setBoardSocket(self, boardSocket: depthai.CameraBoardSocket)

Kind: Method

Specify which board socket to use

Parameter ``boardSocket``:
    Board socket to use

###### setCamId(self, arg0: int)

Kind: Method

###### setCamera(self, name: str)

Kind: Method

Specify which camera to use by name

Parameter ``name``:
    Name of the camera to use

###### setColorOrder(self, colorOrder: depthai.ColorCameraProperties.ColorOrder)

Kind: Method

Set color order of preview output images. RGB or BGR

###### setFp16(self, fp16: bool)

Kind: Method

Set fp16 (0..255) data type of preview output frames

###### setFps(self, fps: float)

Kind: Method

Set rate at which camera should produce frames

Parameter ``fps``:
    Rate in frames per second

###### setFrameEventFilter(self, events: list [ depthai.FrameEvent ])

Kind: Method

###### setImageOrientation(self, imageOrientation: depthai.CameraImageOrientation)

Kind: Method

Set camera image orientation

###### setInterleaved(self, interleaved: bool)

Kind: Method

Set planar or interleaved data of preview output frames

###### setIsp3aFps(self, arg0: int)

Kind: Method

Isp 3A rate (auto focus, auto exposure, auto white balance, camera controls
etc.). Default (0) matches the camera FPS, meaning that 3A is running on each
frame. Reducing the rate of 3A reduces the CPU usage on CSS, but also increases
the convergence rate of 3A. Note that camera controls will be processed at this
rate. E.g. if camera is running at 30 fps, and camera control is sent at every
frame, but 3A fps is set to 15, the camera control messages will be processed at
15 fps rate, which will lead to queueing.

###### setIspNumFramesPool(self, arg0: int)

Kind: Method

Set number of frames in isp pool

###### setIspScale()

Kind: Method

###### setNumFramesPool(self, raw: int, isp: int, preview: int, video: int, still: int)

Kind: Method

Set number of frames in all pools

###### setPreviewKeepAspectRatio(self, keep: bool)

Kind: Method

Specifies whether preview output should preserve aspect ratio, after downscaling
from video size or not.

Parameter ``keep``:
    If true, a larger crop region will be considered to still be able to create
    the final image in the specified aspect ratio. Otherwise video size is
    resized to fit preview size

###### setPreviewNumFramesPool(self, arg0: int)

Kind: Method

Set number of frames in preview pool

###### setPreviewSize()

Kind: Method

###### setRawNumFramesPool(self, arg0: int)

Kind: Method

Set number of frames in raw pool

###### setRawOutputPacked(self, packed: bool)

Kind: Method

Configures whether the camera `raw` frames are saved as MIPI-packed to memory.
The packed format is more efficient, consuming less memory on device, and less
data to send to host: RAW10: 4 pixels saved on 5 bytes, RAW12: 2 pixels saved on
3 bytes. When packing is disabled (`false`), data is saved lsb-aligned, e.g. a
RAW10 pixel will be stored as uint16, on bits 9..0: 0b0000'00pp'pppp'pppp.
Default is auto: enabled for standard color/monochrome cameras where ISP can
work with both packed/unpacked, but disabled for other cameras like ToF.

###### setResolution(self, resolution: depthai.ColorCameraProperties.SensorResolution)

Kind: Method

Set sensor resolution

###### setSensorCrop(self, x: float, y: float)

Kind: Method

Specifies the cropping that happens when converting ISP to video output. By
default, video will be center cropped from the ISP output. Note that this
doesn't actually do on-sensor cropping (and MIPI-stream only that region), but
it does postprocessing on the ISP (on RVC).

Parameter ``x``:
    Top left X coordinate

Parameter ``y``:
    Top left Y coordinate

###### setStillNumFramesPool(self, arg0: int)

Kind: Method

Set number of frames in preview pool

###### setStillSize()

Kind: Method

###### setVideoNumFramesPool(self, arg0: int)

Kind: Method

Set number of frames in preview pool

###### setVideoSize()

Kind: Method

###### frameEvent

Kind: Property

Outputs metadata-only ImgFrame message as an early indicator of an incoming
frame.

It's sent on the MIPI SoF (start-of-frame) event, just after the exposure of the
current frame has finished and before the exposure for next frame starts. Could
be used to synchronize various processes with camera capture. Fields populated:
camera id, sequence number, timestamp

###### initialControl

Kind: Property

Initial control options to apply to sensor

###### inputControl

Kind: Property

Input for CameraControl message, which can modify camera parameters in runtime

###### isp

Kind: Property

Outputs ImgFrame message that carries YUV420 planar (I420/IYUV) frame data.

Generated by the ISP engine, and the source for the 'video', 'preview' and
'still' outputs

###### preview

Kind: Property

Outputs ImgFrame message that carries BGR/RGB planar/interleaved encoded frame
data.

Suitable for use with NeuralNetwork node

###### raw

Kind: Property

Outputs ImgFrame message that carries RAW10-packed (MIPI CSI-2 format) frame
data.

Captured directly from the camera sensor, and the source for the 'isp' output.

###### still

Kind: Property

Outputs ImgFrame message that carries NV12 encoded (YUV420, UV plane
interleaved) frame data.

The message is sent only when a CameraControl message arrives to inputControl
with captureStill command set.

###### video

Kind: Property

Outputs ImgFrame message that carries NV12 encoded (YUV420, UV plane
interleaved) frame data.

Suitable for use with VideoEncoder node

##### depthai.node.Depth(depthai.DeviceNodeGroup)

Kind: Class

Depth node. Unified depth output from StereoDepth, NeuralDepth,
NeuralAssistedStereo, ToF, or GPUStereo.

With Algorithm::AUTO, the backend is chosen from device capabilities, target
FPS, and stereo resolution. On RVC4 this prefers NeuralDepth when available; on
other platforms it uses ToF when a ToF sensor is connected, otherwise
StereoDepth.

Use build() to pin algorithm, FPS, or resolution before the first depth() /
confidence() access. Use setAlignTo() to align depth to another camera output.

###### depthai.node.Depth.Algorithm

Kind: Class

Backend selection for the Depth node.

Members:

  AUTO

  STEREO

  NEURAL

  NEURAL_ASSISTED_STEREO

  TOF

  GPU_STEREO

###### AUTO: typing.ClassVar[Depth.Algorithm]

Kind: Class Variable

###### GPU_STEREO: typing.ClassVar[Depth.Algorithm]

Kind: Class Variable

###### NEURAL: typing.ClassVar[Depth.Algorithm]

Kind: Class Variable

###### NEURAL_ASSISTED_STEREO: typing.ClassVar[Depth.Algorithm]

Kind: Class Variable

###### STEREO: typing.ClassVar[Depth.Algorithm]

Kind: Class Variable

###### TOF: typing.ClassVar[Depth.Algorithm]

Kind: Class Variable

###### __members__: typing.ClassVar[dict[str, Depth.Algorithm]]

Kind: Class Variable

###### __eq__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __getstate__(self) -> int: int

Kind: Method

###### __hash__(self) -> int: int

Kind: Method

###### __index__(self) -> int: int

Kind: Method

###### __init__(self, value: int)

Kind: Method

###### __int__(self) -> int: int

Kind: Method

###### __ne__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __repr__(self) -> str: str

Kind: Method

###### __setstate__(self, state: int)

Kind: Method

###### __str__(self) -> str: str

Kind: Method

###### name

Kind: Property

###### value

Kind: Property

###### build()

Kind: Method

###### getRequestedAlgorithm(self) -> Depth.Algorithm: Depth.Algorithm

Kind: Method

Get the requested algorithm selection.

###### getRequestedConfig(self) -> typing.Any: typing.Any

Kind: Method

Get the requested config override, if any.

Returns:
    Config override, or std::nullopt when config is auto-picked

###### getResolvedAlgorithm(self) -> Depth.Algorithm: Depth.Algorithm

Kind: Method

Get the algorithm actually wired (AUTO resolved). Valid after first depth()
access.

###### getResolvedConfig(self) -> typing.Any: typing.Any

Kind: Method

Get the resolved algorithm-specific config.

###### setAlgorithm(self, algorithm: Depth.Algorithm) -> Depth: Depth

Kind: Method

Set the requested algorithm before wiring.

Parameter ``algorithm``:
    Backend to use; AUTO re-enables auto-selection

###### setAlignTo(self, alignTo: depthai.Node.Output) -> Depth: Depth

Kind: Method

Align depth output to another image source. Must be called before first depth()
or confidence() access. Only depth() is aligned; confidence() stays in the
backend frame.

Parameter ``alignTo``:
    Output to align depth to

###### setConfig()

Kind: Method

###### confidence

Kind: Property

Output confidence map from the active backend. When ToF is active, this forwards
the actual ToF confidence output.

###### depth

Kind: Property

Output depth map from the active backend.

##### depthai.node.DetectionNetwork(depthai.DeviceNodeGroup)

Kind: Class

DetectionNetwork, base for different network specializations

###### depthai.node.DetectionNetwork.Model

Kind: Class

###### __init__()

Kind: Method

###### __init__(self, input: depthai.Node.Output, nnArchive: depthai.NNArchive, confidenceThreshold: float = 0.5)

Kind: Method

###### build()

Kind: Method

###### getClasses(self) -> list [ str ]|None: list [ str ]|None

Kind: Method

###### getConfidenceThreshold(self) -> float: float

Kind: Method

Retrieves threshold at which to filter the rest of the detections.

Returns:
    Detection confidence

###### getNumInferenceThreads(self) -> int: int

Kind: Method

How many inference threads will be used to run the network

Returns:
    Number of threads, 0, 1 or 2. Zero means AUTO

###### setBackend(self, setBackend: str)

Kind: Method

Specifies backend to use

Parameter ``backend``:
    String specifying backend to use

###### setBackendProperties(self, setBackendProperties: dict [ str , str ])

Kind: Method

Set backend properties

Parameter ``backendProperties``:
    backend properties map

###### setBlob()

Kind: Method

###### setBlobPath(self, path: os.PathLike)

Kind: Method

Load network blob into assets and use once pipeline is started.

Throws:
    Error if file doesn't exist or isn't a valid network blob.

Parameter ``path``:
    Path to network blob

###### setConfidenceThreshold(self, thresh: float)

Kind: Method

Specifies confidence threshold at which to filter the rest of the detections.

Parameter ``thresh``:
    Detection confidence must be greater than specified threshold to be added to
    the list

###### setFromModelZoo(self, description: depthai.NNModelDescription, useCached: bool = False)

Kind: Method

Download model from zoo and set it for this Node

Parameter ``description:``:
    Model description to download

Parameter ``useCached:``:
    Use cached model if available

###### setModelPath(self, modelPath: os.PathLike)

Kind: Method

Load network model into assets.

Parameter ``modelPath``:
    Path to the model file.

###### setNNArchive()

Kind: Method

###### setNumInferenceThreads(self, numThreads: int)

Kind: Method

How many threads should the node use to run the network.

Parameter ``numThreads``:
    Number of threads to dedicate to this node

###### setNumNCEPerInferenceThread(self, numNCEPerThread: int)

Kind: Method

How many Neural Compute Engines should a single thread use for inference

Parameter ``numNCEPerThread``:
    Number of NCE per thread

###### setNumPoolFrames(self, numFrames: int)

Kind: Method

Specifies how many frames will be available in the pool

Parameter ``numFrames``:
    How many frames will pool have

###### setNumShavesPerInferenceThread(self, numShavesPerInferenceThread: int)

Kind: Method

How many Shaves should a single thread use for inference

Parameter ``numShavesPerThread``:
    Number of shaves per thread

###### detectionParser

Kind: Property

###### input

Kind: Property

Input message with data to be inferred upon

###### neuralNetwork

Kind: Property

###### out

Kind: Property

Outputs ImgDetections message that carries parsed detection results. Overrides
NeuralNetwork 'out' with ImgDetections output message type.

###### outNetwork

Kind: Property

Outputs unparsed inference results.

###### passthrough

Kind: Property

Passthrough message on which the inference was performed.

Suitable for when input queue is set to non-blocking behavior.

##### depthai.node.DetectionParser(depthai.DeviceNode)

Kind: Class

DetectionParser node. Parses detection results from Mobilenet-SSD or YOLO neural
networks. @note If multiple detection heads are present in the NNArchive, only
one type is supported (either YOLO or Mobilenet-SSD) and the last one will be
used.

###### build()

Kind: Method

###### getAnchorMasks(self) -> dict [ str, list [ int ] ]: dict [ str, list [ int ] ]

Kind: Method

Get anchor masks for anchor-based yolo models

###### getAnchors(self) -> list [ float ]: list [ float ]

Kind: Method

Get anchors for anchor-based yolo models

###### getClasses(self) -> list [ str ]|None: list [ str ]|None

Kind: Method

Get class names to decode.

###### getConfidenceThreshold(self) -> float: float

Kind: Method

Retrieves threshold at which to filter the rest of the detections.

Returns:
    Detection confidence

###### getCoordinateSize(self) -> int: int

Kind: Method

Get number of coordinates per bounding box.

###### getDecodeKeypoints(self) -> bool: bool

Kind: Method

Get whether keypoints decoding is enabled.

###### getDecodeSegmentation(self) -> bool: bool

Kind: Method

Get whether segmentation mask decoding is enabled.

###### getIouThreshold(self) -> float: float

Kind: Method

Get IOU threshold for non-maxima suppression

###### getNNFamily(self) -> depthai.DetectionNetworkType: depthai.DetectionNetworkType

Kind: Method

Gets NN Family to parse

###### getNkeypoints(self) -> int: int

Kind: Method

Get number of keypoints to decode.

###### getNumClasses(self) -> int: int

Kind: Method

Get number of classes to decode.

###### getNumFramesPool(self) -> int: int

Kind: Method

Returns number of frames in pool

###### getStrides(self) -> list [ int ]: list [ int ]

Kind: Method

Get strides for yolo models

###### getSubtype(self) -> str: str

Kind: Method

Get subtype for the parser.

###### runOnHost(self) -> bool: bool

Kind: Method

Check if the node is set to run on host

###### setAnchorMasks(self, anchorMasks: dict [ str , list [ int ] ])

Kind: Method

Set anchor masks for anchor-based yolo models

Parameter ``anchorMasks``:
    Map of anchor masks

###### setAnchors()

Kind: Method

###### setBlob()

Kind: Method

###### setBlobPath(self, path: os.PathLike)

Kind: Method

Load network blob into assets and use once pipeline is started.

Throws:
    Error if file doesn't exist or isn't a valid network blob.

Parameter ``path``:
    Path to network blob

###### setClasses(self, classes: list [ str ])

Kind: Method

Set class names. This will clear any previously set number of classes.

Parameter ``classes``:
    Vector of class names

###### setConfidenceThreshold(self, thresh: float)

Kind: Method

Specifies confidence threshold at which to filter the rest of the detections.

Parameter ``thresh``:
    Detection confidence must be greater than specified threshold to be added to
    the list

###### setCoordinateSize(self, coordinates: int)

Kind: Method

Sets the number of coordinates per bounding box.

Parameter ``coordinates``:
    Number of coordinates. Default is 4

###### setDecodeKeypoints(self, decode: bool)

Kind: Method

Enable/disable keypoints decoding. If enabled, number of keypoints must also be
set.

###### setDecodeSegmentation(self, decode: bool)

Kind: Method

Enable/disable segmentation mask decoding.

###### setInputImageSize()

Kind: Method

###### setIouThreshold(self, thresh: float)

Kind: Method

Set IOU threshold for non-maxima suppression

Parameter ``thresh``:
    IOU threshold

###### setKeypointEdges(self, edges: list [ typing.Annotated [ list [ int ], pybind11_stubgen.typing_ext.FixedSize ( 2 ) ] ])

Kind: Method

Set edges connections between keypoints.

Parameter ``edges``:
    Vector edges connections represented as pairs of keypoint indices. @note
    This is only applicable if keypoints decoding is enabled.

###### setNNArchive(self, nnArchive: depthai.NNArchive)

Kind: Method

Set NNArchive for this Node. If the archive's type is SUPERBLOB, use default
number of shaves.

Parameter ``nnArchive:``:
    NNArchive to set

###### setNNArchiveHead(self, head: depthai.nn_archive.v1.Head)

Kind: Method

Set NNArchive head for this Node.

Parameter ``head:``:
    NNArchive head to set

###### setNNFamily(self, type: depthai.DetectionNetworkType)

Kind: Method

Sets NN Family to parse. Possible values are:

DetectionNetworkType::YOLO - 0 DetectionNetworkType::MOBILENET - 1

.. warning::
    If NN Family is set manually, user must ensure that it matches the actual
    model being used.

###### setNumClasses(self, numClasses: int)

Kind: Method

Set number of classes. This will clear any previously set class names.

Parameter ``numClasses``:
    Number of classes

###### setNumFramesPool(self, numFramesPool: int)

Kind: Method

Specify number of frames in pool.

Parameter ``numFramesPool``:
    How many frames should the pool have

###### setNumKeypoints(self, numKeypoints: int)

Kind: Method

Set number of keypoints to decode. Automatically enables keypoints decoding.

###### setRunOnHost(self, runOnHost: bool)

Kind: Method

Specify whether to run on host or device By default, the node will run on
device.

###### setStrides(self, strides: list [ int ])

Kind: Method

Set strides for yolo models

###### setSubtype(self, subtype: str)

Kind: Method

Set subtype for the parser.

Parameter ``subtype``:
    Subtype string, currently supported subtypes are: yolov6r1, yolov6r2
    yolov8n, yolov6, yolov8, yolov10, yolov11, yolov3, yolov3-tiny, yolov5,
    yolov7, yolo-p, yolov5-u

###### input

Kind: Property

Input NN results with detection data to parse Default queue is blocking with
size 5

###### out

Kind: Property

Outputs image frame with detected edges

##### depthai.node.DynamicCalibration(depthai.DeviceNode)

Kind: Class

###### runOnHost(self) -> bool: bool

Kind: Method

###### setRunOnHost(self, runOnHost: bool)

Kind: Method

Specify whether to run on host or device By default, the node will run on host
on RVC2 and on device on RVC4.

###### calibrationOutput

Kind: Property

Output calibration quality result

###### coverageOutput

Kind: Property

###### inputControl

Kind: Property

Input DynamicCalibrationControl message with ability to modify parameters in
runtime.

###### inputs

Kind: Property

###### left

Kind: Property

###### metricsOutput

Kind: Property

###### qualityOutput

Kind: Property

###### rgb

Kind: Property

###### right

Kind: Property

###### sync

Kind: Property

##### depthai.node.EdgeDetector(depthai.DeviceNode)

Kind: Class

EdgeDetector node. Performs edge detection using 3x3 Sobel filter

###### setMaxOutputFrameSize(self, arg0: int)

Kind: Method

Specify maximum size of output image.

Parameter ``maxFrameSize``:
    Maximum frame size in bytes

###### setNumFramesPool(self, arg0: int)

Kind: Method

Specify number of frames in pool.

Parameter ``numFramesPool``:
    How many frames should the pool have

###### initialConfig

Kind: Property

Initial config to use for edge detection.

###### inputConfig

Kind: Property

Input EdgeDetectorConfig message with ability to modify parameters in runtime.
Default queue is non-blocking with size 4.

###### inputImage

Kind: Property

Input image on which edge detection is performed. Default queue is non-blocking
with size 4.

###### outputImage

Kind: Property

Outputs image frame with detected edges

##### depthai.node.FeatureTracker(depthai.DeviceNode)

Kind: Class

FeatureTracker node. Performs feature tracking and reidentification using motion
estimation between 2 consecutive frames.

###### setHardwareResources(self, numShaves: int, numMemorySlices: int)

Kind: Method

Specify allocated hardware resources for feature tracking. 2 shaves/memory
slices are required for optical flow, 1 for corner detection only.

Parameter ``numShaves``:
    Number of shaves. Maximum 2.

Parameter ``numMemorySlices``:
    Number of memory slices. Maximum 2.

###### initialConfig

Kind: Property

Initial config to use for feature tracking.

###### inputConfig

Kind: Property

Input FeatureTrackerConfig message with ability to modify parameters in runtime.
Default queue is non-blocking with size 4.

###### inputImage

Kind: Property

Input message with frame data on which feature tracking is performed. Default
queue is non-blocking with size 4.

###### outputFeatures

Kind: Property

Outputs TrackedFeatures message that carries tracked features results.

###### passthroughInputImage

Kind: Property

Passthrough message on which the calculation was performed. Suitable for when
input queue is set to non-blocking behavior.

##### depthai.node.GPUStereo(depthai.DeviceNode)

Kind: Class

GPU-accelerated stereo depth node for RVC4.

Computes disparity and depth maps from a synchronized stereo camera pair using
OpenCL on the Adreno GPU. Supports both rectified and unrectified inputs
(controlled via setRectification).

###### build(self, leftInput: depthai.Node.Output, rightInput: depthai.Node.Output) -> GPUStereo: GPUStereo

Kind: Method

Build the node by linking left and right camera outputs.

###### setRectification(self, enable: bool) -> GPUStereo: GPUStereo

Kind: Method

Enable or disable built-in stereo rectification.

When enabled, the node rectifies the input images internally using calibration
data. When disabled, inputs are expected to be already rectified.

###### confidenceMap

Kind: Property

Outputs ImgFrame message that carries RAW8 confidence map. Lower values mean
lower confidence of the calculated disparity value. Note: postprocessing steps
like LR-check/median filter are not applied to confidence map.

###### depth

Kind: Property

Outputs ImgFrame message that carries RAW16 encoded (0..65535) depth data in
depth units (millimeter by default).

Non-determined / invalid depth values are set to 0

###### disparity

Kind: Property

Outputs ImgFrame message that carries RAW16 encoded disparity data.

###### initialConfig

Kind: Property

Initial config to use for GPUStereo.

Use this to configure startup parameters before the pipeline starts. Note: Only
`confidenceThreshold` is supported/exposed for this node.

###### left

Kind: Property

###### right

Kind: Property

##### depthai.node.Gate(depthai.DeviceNode)

Kind: Class

Gate Node.

This node acts as a valve for data pipelines. It controls the flow of messages
from the 'input' to the 'output' based on the state configured via
'inputControl'. It can be configured to stay open indefinitely, stay closed, or
open for a specific number of messages.

###### runOnHost(self) -> bool: bool

Kind: Method

Check if the node is configured to run on the host.

Returns:
    true if running on host, false otherwise.

###### setRunOnHost(self, runOnHost: bool)

Kind: Method

Specify whether to run on host or device By default, the node will run on
device.

###### initialConfig

Kind: Property

Initial config of the node.

###### initialConfig.setter(self, arg1: depthai.GateControl)

Kind: Method

###### input

Kind: Property

Main data input. * Accepts arbitrary Buffer messages (e.g., ImgFrame, NNData).
If the Gate is Open, messages received here are forwarded to 'output'. If the
Gate is Closed, messages received here are discarded/dropped. * Default queue
size: 1 Blocking: False

###### inputControl

Kind: Property

Control input. * Accepts 'GateControl' messages to dynamically change the Gate's
state. Use this to Open/Close the gate or set it to pass a specific number of
frames at runtime. * Default queue size: 4

###### output

Kind: Property

Main data output. * Forwards messages that were allowed through the Gate. The
data type matches the input message.

##### depthai.node.HostNode(depthai.node.ThreadedHostNode)

Kind: Class

###### __init_subclass__

Kind: Class Method

###### __init__(self)

Kind: Method

###### createSubnode(self, class_, args, kwargs)

Kind: Method

###### onStart(self)

Kind: Method

###### onStop(self)

Kind: Method

###### processGroup(self, arg0: depthai.MessageGroup) -> depthai.Buffer: depthai.Buffer

Kind: Method

###### runSyncingOnDevice(self)

Kind: Method

###### runSyncingOnHost(self)

Kind: Method

###### sendProcessingToPipeline(self, arg0: bool)

Kind: Method

Send processing to pipeline. If set to true, it's important to call
`pipeline.run()` in the main thread or `pipeline.processTasks()` in the main
thread. Otherwise, if set to false, such action is not needed.

###### inputs

Kind: Property

###### out

Kind: Property

##### depthai.node.IMU(depthai.DeviceNode)

Kind: Class

IMU node for BNO08X.

###### enableFirmwareUpdate(self, arg0: bool)

Kind: Method

Whether to perform firmware update or not. Default value: false.

###### enableIMUSensor()

Kind: Method

###### getBatchReportThreshold(self) -> int: int

Kind: Method

Above this packet threshold data will be sent to host, if queue is not blocked

###### getMaxBatchReports(self) -> int: int

Kind: Method

Maximum number of IMU packets in a batch report

###### setBatchReportThreshold(self, batchReportThreshold: int)

Kind: Method

Above this packet threshold data will be sent to host, if queue is not blocked

###### setMaxBatchReports(self, maxBatchReports: int)

Kind: Method

Maximum number of IMU packets in a batch report

###### mockIn

Kind: Property

Mock IMU data for replaying recorded data

###### out

Kind: Property

Outputs IMUData message that carries IMU packets.

##### depthai.node.ImageAlign(depthai.DeviceNode)

Kind: Class

ImageAlign node. Calculates spatial location data on a set of ROIs on depth map.

###### runOnHost(self) -> bool: bool

Kind: Method

Check if the node is set to run on host

###### setInterpolation(self, interp: depthai.Interpolation) -> ImageAlign: ImageAlign

Kind: Method

Specify interpolation method to use when resizing

###### setNumFramesPool(self, numFramesPool: int) -> ImageAlign: ImageAlign

Kind: Method

Specify number of frames in the pool

###### setNumShaves(self, numShaves: int) -> ImageAlign: ImageAlign

Kind: Method

Specify number of shaves to use for this node

###### setOutKeepAspectRatio(self, keep: bool) -> ImageAlign: ImageAlign

Kind: Method

Specify whether to keep aspect ratio when resizing

###### setOutputSize(self, alignWidth: int, alignHeight: int) -> ImageAlign: ImageAlign

Kind: Method

Specify the output size of the aligned image

###### setRunOnHost(self, runOnHost: bool)

Kind: Method

Specify whether to run on host or device By default, the node will run on
device.

###### initialConfig

Kind: Property

Initial config to use when calculating spatial location data.

###### input

Kind: Property

Input message. Default queue is non-blocking with size 4.

###### inputAlignTo

Kind: Property

Input align to message. Default queue is non-blocking with size 1.

###### inputConfig

Kind: Property

Input message with ability to modify parameters in runtime. Default queue is
non-blocking with size 4.

###### outputAligned

Kind: Property

Outputs ImgFrame message that is aligned to inputAlignTo.

###### passthroughInput

Kind: Property

Passthrough message on which the calculation was performed. Suitable for when
input queue is set to non-blocking behavior.

##### depthai.node.ImageFilters(depthai.DeviceNode)

Kind: Class

###### build()

Kind: Method

###### runOnHost(self) -> bool: bool

Kind: Method

Check if the node is set to run on host

###### setRunOnHost(self, runOnHost: bool)

Kind: Method

Specify whether to run on host or device By default, the node will run on
device.

###### initialConfig

Kind: Property

Initial config for image filters.

###### input

Kind: Property

Input for image frames to be filtered

###### inputConfig

Kind: Property

Config to be set for a specific filter

###### output

Kind: Property

Filtered frame

##### depthai.node.ImageManip(depthai.DeviceNode)

Kind: Class

ImageManip node. Capability to crop, resize, warp, ... incoming image frames

###### depthai.node.ImageManip.Backend

Kind: Class

Members:

  HW

  CPU

  GPU

  AUTO

###### AUTO: typing.ClassVar[depthai.ImageManipProperties.Backend]

Kind: Class Variable

###### CPU: typing.ClassVar[depthai.ImageManipProperties.Backend]

Kind: Class Variable

###### GPU: typing.ClassVar[depthai.ImageManipProperties.Backend]

Kind: Class Variable

###### HW: typing.ClassVar[depthai.ImageManipProperties.Backend]

Kind: Class Variable

###### __members__: typing.ClassVar[dict[str, depthai.ImageManipProperties.Backend]]

Kind: Class Variable

###### __eq__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __getstate__(self) -> int: int

Kind: Method

###### __hash__(self) -> int: int

Kind: Method

###### __index__(self: depthai.ImageManipProperties.Backend) -> int: int

Kind: Method

###### __init__(self: depthai.ImageManipProperties.Backend, value: int)

Kind: Method

###### __int__(self: depthai.ImageManipProperties.Backend) -> int: int

Kind: Method

###### __ne__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __repr__(self) -> str: str

Kind: Method

###### __setstate__(self: depthai.ImageManipProperties.Backend, state: int)

Kind: Method

###### __str__(self) -> str: str

Kind: Method

###### name

Kind: Property

###### value

Kind: Property

###### depthai.node.ImageManip.PerformanceMode

Kind: Class

Members:

  BALANCED

  PERFORMANCE

  LOW_POWER

###### BALANCED: typing.ClassVar[depthai.ImageManipProperties.PerformanceMode]

Kind: Class Variable

###### LOW_POWER: typing.ClassVar[depthai.ImageManipProperties.PerformanceMode]

Kind: Class Variable

###### PERFORMANCE: typing.ClassVar[depthai.ImageManipProperties.PerformanceMode]

Kind: Class Variable

###### __members__: typing.ClassVar[dict[str, depthai.ImageManipProperties.PerformanceMode]]

Kind: Class Variable

###### __eq__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __getstate__(self) -> int: int

Kind: Method

###### __hash__(self) -> int: int

Kind: Method

###### __index__(self: depthai.ImageManipProperties.PerformanceMode) -> int: int

Kind: Method

###### __init__(self: depthai.ImageManipProperties.PerformanceMode, value: int)

Kind: Method

###### __int__(self: depthai.ImageManipProperties.PerformanceMode) -> int: int

Kind: Method

###### __ne__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __repr__(self) -> str: str

Kind: Method

###### __setstate__(self: depthai.ImageManipProperties.PerformanceMode, state: int)

Kind: Method

###### __str__(self) -> str: str

Kind: Method

###### name

Kind: Property

###### value

Kind: Property

###### setBackend(self, arg0: depthai.ImageManipProperties.Backend) -> ImageManip: ImageManip

Kind: Method

Set backend preference: - CPU: Run ImageManip on the CPU. - HW: Prefer the
dedicated hardware image manipulation backend. - GPU: Prefer the GPU backend. -
AUTO: Let the runtime select the backend automatically (GPU with CPU fallback).

Hardware-accelerated backends can cause some unexpected behavior when using
multiple ImageManip nodes in series. Currently, the only operation affected is
downscaling.

Parameter ``backend``:
    Backend preference

###### setMaxOutputFrameSize(self, arg0: int)

Kind: Method

Specify maximum size of output image.

Parameter ``maxFrameSize``:
    Maximum frame size in bytes

###### setNumFramesPool(self, arg0: int)

Kind: Method

Specify number of frames in pool.

Parameter ``numFramesPool``:
    How many frames should the pool have

###### setPerformanceMode(self, arg0: depthai.ImageManipProperties.PerformanceMode) -> ImageManip: ImageManip

Kind: Method

Set performance mode

Parameter ``performanceMode``:
    Performance mode

###### setRunOnHost(self, arg0: bool) -> ImageManip: ImageManip

Kind: Method

Specify whether to run on host or device

Parameter ``runOnHost``:
    Run node on host

###### initialConfig

Kind: Property

Initial config to use when manipulating frames

###### inputConfig

Kind: Property

Input ImageManipConfig message with ability to modify parameters in runtime

###### inputImage

Kind: Property

Input image to be modified

###### out

Kind: Property

##### depthai.node.MessageDemux(depthai.DeviceNode)

Kind: Class

###### getProcessor(self) -> depthai.ProcessorType: depthai.ProcessorType

Kind: Method

Get on which processor the node should run

Returns:
    Processor type - Leon CSS or Leon MSS

###### setProcessor(self, arg0: depthai.ProcessorType)

Kind: Method

Specify on which processor the node should run. RVC2 only.

Parameter ``type``:
    Processor type - Leon CSS or Leon MSS

###### input

Kind: Property

Input message of type MessageGroup

###### outputs

Kind: Property

A map of outputs, where keys are same as in the input MessageGroup

##### depthai.node.MonoCamera(depthai.DeviceNode)

Kind: Class

MonoCamera node. For use with grayscale sensors.

###### getBoardSocket(self) -> depthai.CameraBoardSocket: depthai.CameraBoardSocket

Kind: Method

Retrieves which board socket to use

Returns:
    Board socket to use

###### getCamId(self) -> int: int

Kind: Method

###### getCamera(self) -> str: str

Kind: Method

Retrieves which camera to use by name

Returns:
    Name of the camera to use

###### getFps(self) -> float: float

Kind: Method

Get rate at which camera should produce frames

Returns:
    Rate in frames per second

###### getFrameEventFilter(self) -> list [ depthai.FrameEvent ]: list [ depthai.FrameEvent ]

Kind: Method

###### getImageOrientation(self) -> depthai.CameraImageOrientation: depthai.CameraImageOrientation

Kind: Method

Get camera image orientation

###### getNumFramesPool(self) -> int: int

Kind: Method

Get number of frames in main (ISP output) pool

###### getRawNumFramesPool(self) -> int: int

Kind: Method

Get number of frames in raw pool

###### getResolution(self) -> depthai.MonoCameraProperties.SensorResolution: depthai.MonoCameraProperties.SensorResolution

Kind: Method

Get sensor resolution

###### getResolutionHeight(self) -> int: int

Kind: Method

Get sensor resolution height

###### getResolutionSize(self) -> tuple [ int, int ]: tuple [ int, int ]

Kind: Method

Get sensor resolution as size

###### getResolutionWidth(self) -> int: int

Kind: Method

Get sensor resolution width

###### setBoardSocket(self, boardSocket: depthai.CameraBoardSocket)

Kind: Method

Specify which board socket to use

Parameter ``boardSocket``:
    Board socket to use

###### setCamId(self, arg0: int)

Kind: Method

###### setCamera(self, name: str)

Kind: Method

Specify which camera to use by name

Parameter ``name``:
    Name of the camera to use

###### setFps(self, fps: float)

Kind: Method

Set rate at which camera should produce frames

Parameter ``fps``:
    Rate in frames per second

###### setFrameEventFilter(self, events: list [ depthai.FrameEvent ])

Kind: Method

###### setImageOrientation(self, imageOrientation: depthai.CameraImageOrientation)

Kind: Method

Set camera image orientation

###### setIsp3aFps(self, arg0: int)

Kind: Method

Isp 3A rate (auto focus, auto exposure, auto white balance, camera controls
etc.). Default (0) matches the camera FPS, meaning that 3A is running on each
frame. Reducing the rate of 3A reduces the CPU usage on CSS, but also increases
the convergence rate of 3A. Note that camera controls will be processed at this
rate. E.g. if camera is running at 30 fps, and camera control is sent at every
frame, but 3A fps is set to 15, the camera control messages will be processed at
15 fps rate, which will lead to queueing.

###### setNumFramesPool(self, arg0: int)

Kind: Method

Set number of frames in main (ISP output) pool

###### setRawNumFramesPool(self, arg0: int)

Kind: Method

Set number of frames in raw pool

###### setRawOutputPacked(self, packed: bool)

Kind: Method

Configures whether the camera `raw` frames are saved as MIPI-packed to memory.
The packed format is more efficient, consuming less memory on device, and less
data to send to host: RAW10: 4 pixels saved on 5 bytes, RAW12: 2 pixels saved on
3 bytes. When packing is disabled (`false`), data is saved lsb-aligned, e.g. a
RAW10 pixel will be stored as uint16, on bits 9..0: 0b0000'00pp'pppp'pppp.
Default is auto: enabled for standard color/monochrome cameras where ISP can
work with both packed/unpacked, but disabled for other cameras like ToF.

###### setResolution(self, resolution: depthai.MonoCameraProperties.SensorResolution)

Kind: Method

Set sensor resolution

###### frameEvent

Kind: Property

###### initialControl

Kind: Property

Initial control options to apply to sensor

###### inputControl

Kind: Property

###### out

Kind: Property

###### raw

Kind: Property

##### depthai.node.NeuralAssistedStereo(depthai.DeviceNode)

Kind: Class

NeuralAssistedStereo node. Combines Neural Depth with VPP and traditional Stereo
Depth.

This composite node internally creates and connects: - Rectification node (full
resolution) - NeuralDepth node (low resolution depth estimation) - VPP node
(applies virtual projection pattern) - StereoDepth node (final depth computation
on VPP-enhanced images)

Pipeline structure: Left/Right Cameras → Rectification → [Full res to VPP] ↓
NeuralDepth (low res) → [disparity + confidence to VPP] ↓ VPP (combines neural
depth with full res images) ↓ StereoDepth → Final Depth Output

###### build(self, leftInput: depthai.Node.Output, rightInput: depthai.Node.Output, neuralModel: depthai.DeviceModelZoo = ..., rectifyImages: bool = True) -> NeuralAssistedStereo: NeuralAssistedStereo

Kind: Method

###### depth

Kind: Property

###### disparity

Kind: Property

###### inputNeuralConfig

Kind: Property

###### inputStereoConfig

Kind: Property

###### inputVppConfig

Kind: Property

###### left

Kind: Property

###### neuralConfidence

Kind: Property

###### neuralDepth

Kind: Property

###### neuralDisparity

Kind: Property

###### rectification

Kind: Property

###### rectifiedLeft

Kind: Property

###### rectifiedRight

Kind: Property

###### right

Kind: Property

###### stereoDepth

Kind: Property

###### vpp

Kind: Property

###### vppLeft

Kind: Property

###### vppRight

Kind: Property

##### depthai.node.NeuralDepth(depthai.DeviceNode)

Kind: Class

NeuralDepth node. Compute depth from left-right image pair using neural network.

###### getInputSize(model: depthai.DeviceModelZoo) -> tuple [ int, int ]: tuple [ int, int ]

Kind: Static Method

Get input size for specific model

###### build(self, leftInput: depthai.Node.Output, rightInput: depthai.Node.Output, model: depthai.DeviceModelZoo = ...) -> NeuralDepth: NeuralDepth

Kind: Method

###### setRectification(self, enable: bool) -> NeuralDepth: NeuralDepth

Kind: Method

Enable or disable rectification (useful for prerectified inputs)

###### confidence

Kind: Property

Output confidence ImgFrame

###### depth

Kind: Property

Output depth ImgFrame

###### disparity

Kind: Property

Output disparity ImgFrame

###### edge

Kind: Property

Output edge ImgFrame

###### initialConfig

Kind: Property

Initial config to use for NeuralDepth.

###### inputConfig

Kind: Property

Input config to modify parameters in runtime.

###### left

Kind: Property

Input for left ImgFrame of left-right pair

###### messageDemux

Kind: Property

###### neuralNetwork

Kind: Property

###### rectification

Kind: Property

###### rectifiedLeft

Kind: Property

Output for rectified left ImgFrame

###### rectifiedRight

Kind: Property

Output for rectified right ImgFrame

###### right

Kind: Property

Input for right ImgFrame of left-right pair

###### sync

Kind: Property

##### depthai.node.NeuralNetwork(depthai.DeviceNode)

Kind: Class

NeuralNetwork node. Runs a neural inference on input data.

###### depthai.node.NeuralNetwork.Model

Kind: Class

###### __init__()

Kind: Method

###### build()

Kind: Method

###### getNNArchive(self) -> depthai.NNArchive|None: depthai.NNArchive|None

Kind: Method

Get the archive owned by this Node.

Returns:
    constant reference to this Nodes archive

###### getNumInferenceThreads(self) -> int: int

Kind: Method

How many inference threads will be used to run the network

Returns:
    Number of threads, 0, 1 or 2. Zero means AUTO

###### setBackend(self, setBackend: str)

Kind: Method

Specifies backend to use

Parameter ``backend``:
    String specifying backend to use

###### setBackendProperties(self, setBackendProperties: dict [ str , str ])

Kind: Method

Set backend properties

Parameter ``backendProperties``:
    backend properties map

###### setBlob()

Kind: Method

###### setBlobPath(self, path: os.PathLike)

Kind: Method

Load network blob into assets and use once pipeline is started.

Throws:
    Error if file doesn't exist or isn't a valid network blob.

Parameter ``path``:
    Path to network blob

###### setFromModelZoo(self, description: depthai.NNModelDescription, useCached: bool)

Kind: Method

Download model from zoo and set it for this Node

Parameter ``description:``:
    Model description to download

Parameter ``useCached:``:
    Use cached model if available

###### setModelFromDeviceZoo(self, model: depthai.DeviceModelZoo)

Kind: Method

Set model from Device Model Zoo

Parameter ``model``:
    DeviceModelZoo model enum @note Only applicable for RVC4 devices with OS
    1.20.5 or higher

###### setModelPath(self, modelPath: os.PathLike)

Kind: Method

Load network xml and bin files into assets.

Parameter ``xmlModelPath``:
    Path to the neural network model file.

###### setNNArchive()

Kind: Method

###### setNumInferenceThreads(self, numThreads: int)

Kind: Method

How many threads should the node use to run the network.

Parameter ``numThreads``:
    Number of threads to dedicate to this node

###### setNumNCEPerInferenceThread(self, numNCEPerThread: int)

Kind: Method

How many Neural Compute Engines should a single thread use for inference

Parameter ``numNCEPerThread``:
    Number of NCE per thread

###### setNumPoolFrames(self, numFrames: int)

Kind: Method

Specifies how many frames will be available in the pool

Parameter ``numFrames``:
    How many frames will pool have

###### setNumShavesPerInferenceThread(self, numShavesPerInferenceThread: int)

Kind: Method

How many Shaves should a single thread use for inference

Parameter ``numShavesPerThread``:
    Number of shaves per thread

###### input

Kind: Property

Input message with data to be inferred upon

###### inputs

Kind: Property

Inputs mapped to network inputs. Useful for inferring from separate data sources
Default input is non-blocking with queue size 1 and waits for messages

###### out

Kind: Property

Outputs NNData message that carries inference results

###### passthrough

Kind: Property

Passthrough message on which the inference was performed.

Suitable for when input queue is set to non-blocking behavior.

###### passthroughs

Kind: Property

Passthroughs which correspond to specified input

##### depthai.node.ObjectTracker(depthai.DeviceNode)

Kind: Class

ObjectTracker node. Performs object tracking using Kalman filter and hungarian
algorithm.

###### setDetectionLabelsToTrack(self, labels: list [ int ])

Kind: Method

Specify detection labels to track.

Parameter ``labels``:
    Detection labels to track. Default every label is tracked from image
    detection network output.

###### setMaxObjectsToTrack(self, maxObjectsToTrack: int)

Kind: Method

Specify maximum number of object to track.

Parameter ``maxObjectsToTrack``:
    Maximum number of object to track. Maximum 60 in case of SHORT_TERM_KCF,
    otherwise 1000.

###### setOcclusionRatioThreshold(self, threshold: float)

Kind: Method

Set the occlusion ratio threshold. Used to filter out overlapping tracklets.

Parameter ``theshold``:
    Occlusion ratio threshold. Default 0.3.

###### setRunOnHost(self, runOnHost: bool)

Kind: Method

Specify whether to run on host or device By default, the node will run on
device.

###### setSpatialAssociation(self, enabled: bool)

Kind: Method

Enable or disable spatially-aware association. If disabled, only 2D association
is used.

Parameter ``enabled``:
    `true` enables spatially-aware association, `false` uses 2D-only
    association. Default is false.

###### setSpatialAssociationWeight(self, weight: float)

Kind: Method

Set spatial association weight in [0,1].

Parameter ``weight``:
    Spatial association weight in [0,1] used to blend 2D and spatial association
    scores (0 = 2D-only scoring, 1 = spatial-only scoring). This weight affects
    candidate scoring only; final acceptance still requires passing the 2D IoU
    threshold gate. Default is 0.5.

###### setSpatialDepthAwareScale(self, scale: float)

Kind: Method

Set depth-aware gating scale used for spatial association. Increases gating
threshold with increased depth.

Parameter ``scale``:
    Depth-aware gating scale factor. Default is 0.35

###### setSpatialDistanceThreshold(self, thresholdMeters: float)

Kind: Method

Set base 3D gating threshold in meters for spatial association.

Parameter ``thresholdMeters``:
    Base spatial gating distance in meters. Default is 1.5m.

###### setTrackerIdAssignmentPolicy(self, type: depthai.TrackerIdAssignmentPolicy)

Kind: Method

Specify tracker ID assignment policy.

Parameter ``type``:
    Tracker ID assignment policy.

###### setTrackerThreshold(self, threshold: float)

Kind: Method

Specify tracker threshold.

Parameter ``threshold``:
    Above this threshold the detected objects will be tracked. Default 0, all
    image detections are tracked.

###### setTrackerType(self, type: depthai.TrackerType)

Kind: Method

Specify tracker type algorithm.

Parameter ``type``:
    Tracker type.

###### setTrackingPerClass(self, trackingPerClass: bool)

Kind: Method

Whether tracker should take into consideration class label for tracking.

###### setTrackletBirthThreshold(self, trackletBirthThreshold: int)

Kind: Method

Set the tracklet birth threshold. Minimum consecutive tracked frames required to
consider a tracklet as a new (TRACKED) instance.

Parameter ``trackletBirthThreshold``:
    Tracklet birth threshold. Default 3.

###### setTrackletMaxLifespan(self, trackletMaxLifespan: int)

Kind: Method

Set the tracklet lifespan in number of frames. Number of frames after which a
LOST tracklet is removed.

Parameter ``trackletMaxLifespan``:
    Tracklet lifespan in number of frames. Default 120.

###### inputConfig

Kind: Property

Input ObjectTrackerConfig message with ability to modify parameters at runtime.
Default queue is non-blocking with size 4.

###### inputDetectionFrame

Kind: Property

Input ImgFrame message on which object detection was performed. Default queue is
non-blocking with size 4.

###### inputDetections

Kind: Property

Input message with image detection from neural network. Default queue is non-
blocking with size 4.

###### inputTrackerFrame

Kind: Property

Input ImgFrame message on which tracking will be performed. RGBp, BGRp, NV12,
YUV420p types are supported. Default queue is non-blocking with size 4.

###### out

Kind: Property

Outputs Tracklets message that carries object tracking results.

###### passthroughDetectionFrame

Kind: Property

Passthrough ImgFrame message on which object detection was performed. Suitable
for when input queue is set to non-blocking behavior.

###### passthroughDetections

Kind: Property

Passthrough image detections message from neural network output. Suitable for
when input queue is set to non-blocking behavior.

###### passthroughTrackerFrame

Kind: Property

Passthrough ImgFrame message on which tracking was performed. Suitable for when
input queue is set to non-blocking behavior.

##### depthai.node.PointCloud(depthai.DeviceNode)

Kind: Class

PointCloud node. Computes point cloud from depth frames.

###### setNumFramesPool(self, numFramesPool: int)

Kind: Method

Specify number of frames in pool.

Parameter ``numFramesPool``:
    How many frames should the pool have

###### setRunOnHost(self, runOnHost: bool)

Kind: Method

Specify whether to run on host or device By default, the node will run on host.

###### setTargetCoordinateSystem()

Kind: Method

###### useCPU(self)

Kind: Method

Use single-threaded CPU for processing

###### useCPUMT(self, numThreads: int = 2)

Kind: Method

Use multi-threaded CPU for processing

###### useGPU(self, device: int = 0)

Kind: Method

Use GPU for point cloud computation

Parameter ``device``:
    GPU device index (default 0)

###### initialConfig

Kind: Property

Initial config to use when computing the point cloud.

###### inputColor

Kind: Property

###### inputConfig

Kind: Property

Input PointCloudConfig message with ability to modify parameters in runtime.
Default queue is non-blocking with size 4.

###### inputDepth

Kind: Property

###### outputPointCloud

Kind: Property

Outputs PointCloudData message

###### passthroughDepth

Kind: Property

Passthrough depth from which the point cloud was calculated. Suitable for when
input queue is set to non-blocking behavior.

##### depthai.node.RGBD(depthai.node.ThreadedHostNode)

Kind: Class

RGBD node. Combines depth and color frames into a single point cloud.

###### build()

Kind: Method

###### printDevices(self)

Kind: Method

Print available GPU devices

###### setDepthUnits(self, units: depthai.LengthUnit)

Kind: Method

###### useCPU(self)

Kind: Method

Use single-threaded CPU for processing

###### useCPUMT(self, numThreads: int = 2)

Kind: Method

Use multi-threaded CPU for processing

Parameter ``numThreads``:
    Number of threads to use

###### useGPU(self, device: int = 0)

Kind: Method

Use GPU for processing (needs to be compiled with Kompute support)

Parameter ``device``:
    GPU device index

###### inColor

Kind: Property

###### inDepth

Kind: Property

###### pcl

Kind: Property

Output point cloud.

###### rgbd

Kind: Property

Output RGBD frames.

##### depthai.node.RTABMapSLAM(depthai.node.ThreadedHostNode)

Kind: Class

RTABMap SLAM node. Performs SLAM on given odometry pose, rectified frame and
depth frame.

###### getLocalTransform(self) -> depthai.TransformData: depthai.TransformData

Kind: Method

###### saveDatabase(self)

Kind: Method

###### setAlphaScaling(self, alpha: float)

Kind: Method

Set the alpha scaling factor for the camera model.

###### setDatabasePath(self, path: str)

Kind: Method

Set RTABMap database path. "/tmp/rtabmap.tmp.db" by default.

###### setFreq(self, f: float)

Kind: Method

Set the frequency at which the node processes data. 1Hz by default.

###### setLoadDatabaseOnStart(self, load: bool)

Kind: Method

Whether to load the database on start. False by default.

###### setLocalTransform(self, transform: depthai.TransformData)

Kind: Method

###### setParams(self, params: dict [ str , str ])

Kind: Method

Set RTABMap parameters. For the list of all parameters visit

https://github.com/introlab/rtabmap/blob/master/corelib/include/rtabmap/core/Par
ameters.h

###### setPublishGrid(self, publish: bool)

Kind: Method

Whether to publish the ground point cloud. True by default.

###### setPublishGroundCloud(self, publish: bool)

Kind: Method

Whether to publish the ground point cloud. True by default.

###### setPublishObstacleCloud(self, publish: bool)

Kind: Method

Whether to publish the obstacle point cloud. True by default.

###### setSaveDatabaseOnClose(self, save: bool)

Kind: Method

Whether to save the database on close. False by default.

###### setSaveDatabasePeriod(self, period: float)

Kind: Method

Set the interval at which the database is saved. 30.0s by default.

###### setSaveDatabasePeriodically(self, save: bool)

Kind: Method

Whether to save the database periodically. False by default.

###### setUseFeatures(self, useFeatures: bool)

Kind: Method

Whether to use input features for SLAM. False by default.

###### triggerNewMap(self)

Kind: Method

Trigger a new map.

###### depth

Kind: Property

###### features

Kind: Property

Input tracked features on which SLAM is performed (optional).

###### groundPCL

Kind: Property

Output ground point cloud.

###### obstaclePCL

Kind: Property

Output obstacle point cloud.

###### occupancyGridMap

Kind: Property

Output occupancy grid map.

###### odom

Kind: Property

Input odometry pose.

###### odomCorrection

Kind: Property

Output odometry correction (map to odom).

###### passthroughDepth

Kind: Property

Output passthrough depth image.

###### passthroughFeatures

Kind: Property

Output passthrough features.

###### passthroughOdom

Kind: Property

Output passthrough odometry pose.

###### passthroughRect

Kind: Property

Output passthrough rectified image.

###### rect

Kind: Property

###### transform

Kind: Property

Output transform.

##### depthai.node.RTABMapVIO(depthai.node.ThreadedHostNode)

Kind: Class

RTABMap Visual Inertial Odometry node. Performs VIO on rectified frame, depth
frame and IMU data.

###### reset(self, transform: depthai.TransformData)

Kind: Method

Reset Odometry.

###### setLocalTransform(self, transform: depthai.TransformData)

Kind: Method

###### setParams(self, params: dict [ str , str ])

Kind: Method

Set RTABMap parameters.

###### setUseFeatures(self, useFeatures: bool)

Kind: Method

Whether to use input features or calculate them internally.

###### depth

Kind: Property

###### features

Kind: Property

Input tracked features on which VIO is performed (optional).

###### imu

Kind: Property

Input IMU data.

###### passthroughDepth

Kind: Property

Passthrough depth frame.

###### passthroughFeatures

Kind: Property

Passthrough features.

###### passthroughRect

Kind: Property

Passthrough rectified frame.

###### rect

Kind: Property

###### transform

Kind: Property

Output transform.

##### depthai.node.RecordMetadataOnly(depthai.node.ThreadedHostNode)

Kind: Class

RecordMetadataOnly node, used to record a source stream to a file

###### getCompressionLevel(self) -> ...: ...

Kind: Method

###### getRecordFile(self) -> os.PathLike: os.PathLike

Kind: Method

###### setCompressionLevel(self, compressionLevel: ...) -> RecordMetadataOnly: RecordMetadataOnly

Kind: Method

###### setRecordFile(self, recordFile: os.PathLike) -> RecordMetadataOnly: RecordMetadataOnly

Kind: Method

###### input

Kind: Property

Input IMU messages to be recorded (will support other types in the future)

Default queue is blocking with size 8

##### depthai.node.RecordVideo(depthai.node.ThreadedHostNode)

Kind: Class

RecordVideo node, used to record a video source stream to a file

###### getCompressionLevel(self) -> ...: ...

Kind: Method

###### getRecordMetadataFile(self) -> os.PathLike: os.PathLike

Kind: Method

###### getRecordVideoFile(self) -> os.PathLike: os.PathLike

Kind: Method

###### setCompressionLevel(self, compressionLevel: ...) -> RecordVideo: RecordVideo

Kind: Method

###### setFps(self, fps: int) -> RecordVideo: RecordVideo

Kind: Method

###### setRecordMetadataFile(self, recordFile: os.PathLike) -> RecordVideo: RecordVideo

Kind: Method

###### setRecordVideoFile(self, recordFile: os.PathLike) -> RecordVideo: RecordVideo

Kind: Method

###### input

Kind: Property

Input for ImgFrame or EncodedFrame messages to be recorded

Default queue is blocking with size 15

##### depthai.node.Rectification(depthai.DeviceNode)

Kind: Class

###### enableRectification(self, enable: bool) -> Rectification: Rectification

Kind: Method

Enable or disable rectification (useful for minimal changes during debugging)

###### setOutputSize()

Kind: Method

###### setRunOnHost(self, runOnHost: bool)

Kind: Method

Specify whether to run on host or device By default, the node will run on
device.

###### input1

Kind: Property

Input images to be rectified

###### input2

Kind: Property

###### output1

Kind: Property

Send outputs

###### output2

Kind: Property

###### passthrough1

Kind: Property

Passthrough for input messages (so the node can be placed between other nodes)

###### passthrough2

Kind: Property

##### depthai.node.ReplayMetadataOnly(depthai.node.ThreadedHostNode)

Kind: Class

Replay node, used to replay a file to a source node

###### getFps(self) -> float: float

Kind: Method

###### getLoop(self) -> bool: bool

Kind: Method

###### getReplayFile(self) -> os.PathLike: os.PathLike

Kind: Method

###### setFps(self, fps: float) -> ReplayMetadataOnly: ReplayMetadataOnly

Kind: Method

###### setLoop(self, loop: bool) -> ReplayMetadataOnly: ReplayMetadataOnly

Kind: Method

###### setReplayFile(self, replayFile: os.PathLike) -> ReplayMetadataOnly: ReplayMetadataOnly

Kind: Method

###### out

Kind: Property

Output for any type of messages to be transferred over XLink stream

Default queue is blocking with size 8

##### depthai.node.ReplayVideo(depthai.node.ThreadedHostNode)

Kind: Class

Replay node, used to replay a file to a source node

###### getFps(self) -> float: float

Kind: Method

###### getLoop(self) -> bool: bool

Kind: Method

###### getOutFrameType(self) -> depthai.ImgFrame.Type: depthai.ImgFrame.Type

Kind: Method

###### getReplayMetadataFile(self) -> os.PathLike: os.PathLike

Kind: Method

###### getReplayVideoFile(self) -> os.PathLike: os.PathLike

Kind: Method

###### getSize(self) -> tuple [ int, int ]: tuple [ int, int ]

Kind: Method

###### setFps(self, fps: float) -> ReplayVideo: ReplayVideo

Kind: Method

###### setLoop(self, loop: bool) -> ReplayVideo: ReplayVideo

Kind: Method

###### setOutFrameType(self, frameType: depthai.ImgFrame.Type) -> ReplayVideo: ReplayVideo

Kind: Method

###### setReplayMetadataFile(self, replayFile: os.PathLike) -> ReplayVideo: ReplayVideo

Kind: Method

###### setReplayVideoFile(self, replayVideoFile: os.PathLike) -> ReplayVideo: ReplayVideo

Kind: Method

###### setSize()

Kind: Method

###### out

Kind: Property

Output for any type of messages to be transferred over XLink stream

Default queue is blocking with size 8

##### depthai.node.SPIIn(depthai.DeviceNode)

Kind: Class

SPIIn node. Receives messages over SPI.

###### getBusId(self) -> int: int

Kind: Method

Get bus id

###### getMaxDataSize(self) -> int: int

Kind: Method

Get maximum messages size in bytes

###### getNumFrames(self) -> int: int

Kind: Method

Get number of frames in pool

###### getStreamName(self) -> str: str

Kind: Method

Get stream name

###### setBusId(self, id: int)

Kind: Method

Specifies SPI Bus number to use

Parameter ``id``:
    SPI Bus id

###### setMaxDataSize(self, maxDataSize: int)

Kind: Method

Set maximum message size it can receive

Parameter ``maxDataSize``:
    Maximum size in bytes

###### setNumFrames(self, numFrames: int)

Kind: Method

Set number of frames in pool for sending messages forward

Parameter ``numFrames``:
    Maximum number of frames in pool

###### setStreamName(self, name: str)

Kind: Method

Specifies stream name over which the node will receive data

Parameter ``name``:
    Stream name

###### out

Kind: Property

Outputs message of same type as send from host.

##### depthai.node.SPIOut(depthai.DeviceNode)

Kind: Class

SPIOut node. Sends messages over SPI.

###### setBusId(self, id: int)

Kind: Method

Specifies SPI Bus number to use

Parameter ``id``:
    SPI Bus id

###### setStreamName(self, name: str)

Kind: Method

Specifies stream name over which the node will send data

Parameter ``name``:
    Stream name

###### input

Kind: Property

Input for any type of messages to be transferred over SPI stream Default queue
is blocking with size 8

##### depthai.node.Script(depthai.DeviceNode)

Kind: Class

###### getProcessor(self) -> depthai.ProcessorType: depthai.ProcessorType

Kind: Method

Get on which processor the script should run

Returns:
    Processor type - Leon CSS or Leon MSS

###### getScriptName(self) -> str: str

Kind: Method

Get the script name in utf-8.

When name set with setScript() or setScriptPath(), returns that name. When
script loaded with setScriptPath() with name not provided, returns the utf-8
string of that path. Otherwise, returns "<script>"

Returns:
    std::string of script name in utf-8

###### setProcessor(self, arg0: depthai.ProcessorType)

Kind: Method

Set on which processor the script should run

Parameter ``type``:
    Processor type - Leon CSS or Leon MSS

###### setScript()

Kind: Method

###### setScriptPath()

Kind: Method

###### inputs

Kind: Property

###### outputs

Kind: Property

##### depthai.node.SegmentationParser(depthai.DeviceNode)

Kind: Class

SegmentationParser node. Parses raw segmentation output from segmentation neural
networks into a dai::SegmentationMask datatype. The parser supports two output
model types: 1. Single-channel output where the model argmaxes the class
probabilities internally and outputs a single channel mask with class indices.
2. Multi-channel output where each channel corresponds to the probability map
for a specific class. The parser will perform argmax across channels to generate
the final mask. The parser can be configured to treat the first class (index 0)
as the background class, which will be ignored in the final segmentation mask.

.. warning::
    Only OAK4 supports running SegmentationParser on device. On other platforms,
    the node will automatically switch to host execution.

###### build()

Kind: Method

###### getBackgroundClass(self) -> bool: bool

Kind: Method

Gets whether the first class (index 0) is considered the background class.

###### getLabels(self) -> list [ str ]: list [ str ]

Kind: Method

Returns the class labels associated with the segmentation mask.

###### runOnHost(self) -> bool: bool

Kind: Method

Check if the node is set to run on host

###### setBackgroundClass(self, backgroundClass: bool)

Kind: Method

Sets whether the first class (index 0) is considered the background class. If
true, the pixels classified as index 0 will be treated as background.

Parameter ``backgroundClass``:
    Boolean indicating if the first class is the background class

@note Only applicable if the number of classes is greater than 1 and the output
classes are not in a single layer (eg. classesInOneLayer = false).

###### setLabels(self, labels: list [ str ])

Kind: Method

Sets the class labels associated with the segmentation mask. The label at index
$i$ in the `labels` vector corresponds to the value $i$ in the segmentation mask
data array.

Parameter ``labels``:
    Vector of class labels

###### setNNArchive(self, nnArchive: depthai.NNArchive)

Kind: Method

Set NNArchive for this Node.

Parameter ``nnArchive:``:
    NNArchive to set

###### setNNArchiveHead(self, head: depthai.nn_archive.v1.Head)

Kind: Method

Set NNArchive head for this Node.

Parameter ``head:``:
    NNArchive head to set

###### setRunOnHost(self, runOnHost: bool)

Kind: Method

Specify whether to run on host or device By default, the node will run on
device.

###### initialConfig

Kind: Property

Initial config to use when parsing segmentation masks.

###### input

Kind: Property

Input NN results with segmentation data to parser

###### inputConfig

Kind: Property

Input SegmentationParserConfig message with ability to modify parameters in
runtime.

###### out

Kind: Property

Outputs segmentation mask

##### depthai.node.SpatialDetectionNetwork(depthai.DeviceNode)

Kind: Class

SpatialDetectionNetwork node. Runs a neural inference on input image and
calculates spatial location data.

###### depthai.node.SpatialDetectionNetwork.Model

Kind: Class

###### __init__()

Kind: Method

###### build()

Kind: Method

###### getClasses(self) -> list [ str ]|None: list [ str ]|None

Kind: Method

Get classes labels

###### getConfidenceThreshold(self) -> float: float

Kind: Method

Retrieves threshold at which to filter the rest of the detections.

Returns:
    Detection confidence

###### getNumInferenceThreads(self) -> int: int

Kind: Method

How many inference threads will be used to run the network

Returns:
    Number of threads, 0, 1 or 2. Zero means AUTO

###### setBackend(self, setBackend: str)

Kind: Method

Specifies backend to use

Parameter ``backend``:
    String specifying backend to use

###### setBackendProperties(self, setBackendProperties: dict [ str , str ])

Kind: Method

Set backend properties

Parameter ``backendProperties``:
    backend properties map

###### setBlob()

Kind: Method

###### setBlobPath(self, path: os.PathLike)

Kind: Method

Load network blob into assets and use once pipeline is started.

Throws:
    Error if file doesn't exist or isn't a valid network blob.

Parameter ``path``:
    Path to network blob

###### setBoundingBoxScaleFactor(self, scaleFactor: float)

Kind: Method

Custom interface

Specifies scale factor for detected bounding boxes.

Parameter ``scaleFactor``:
    Scale factor must be in the interval (0,1].

###### setConfidenceThreshold(self, thresh: float)

Kind: Method

Specifies confidence threshold at which to filter the rest of the detections.

Parameter ``thresh``:
    Detection confidence must be greater than specified threshold to be added to
    the list

###### setDepthLowerThreshold(self, lowerThreshold: int)

Kind: Method

Specifies lower threshold in depth units (millimeter by default) for depth
values which will used to calculate spatial data

Parameter ``lowerThreshold``:
    LowerThreshold must be in the interval [0,upperThreshold] and less than
    upperThreshold.

###### setDepthUpperThreshold(self, upperThreshold: int)

Kind: Method

Specifies upper threshold in depth units (millimeter by default) for depth
values which will used to calculate spatial data

Parameter ``upperThreshold``:
    UpperThreshold must be in the interval (lowerThreshold,65535].

###### setFromModelZoo(self, description: depthai.NNModelDescription, useCached: bool)

Kind: Method

Download model from zoo and set it for this Node

Parameter ``description:``:
    Model description to download

Parameter ``useCached:``:
    Use cached model if available

###### setModelPath(self, modelPath: os.PathLike)

Kind: Method

Load network file into assets.

Parameter ``modelPath``:
    Path to the model file.

###### setNNArchive()

Kind: Method

###### setNumInferenceThreads(self, numThreads: int)

Kind: Method

How many threads should the node use to run the network.

Parameter ``numThreads``:
    Number of threads to dedicate to this node

###### setNumNCEPerInferenceThread(self, numNCEPerThread: int)

Kind: Method

How many Neural Compute Engines should a single thread use for inference

Parameter ``numNCEPerThread``:
    Number of NCE per thread

###### setNumPoolFrames(self, numFrames: int)

Kind: Method

Specifies how many frames will be available in the pool

Parameter ``numFrames``:
    How many frames will pool have

###### setNumShavesPerInferenceThread(self, numShavesPerInferenceThread: int)

Kind: Method

How many Shaves should a single thread use for inference

Parameter ``numShavesPerThread``:
    Number of shaves per thread

###### setSpatialCalculationAlgorithm(self, calculationAlgorithm: depthai.SpatialLocationCalculatorAlgorithm)

Kind: Method

Specifies spatial location calculator algorithm: Average/Min/Max

Parameter ``calculationAlgorithm``:
    Calculation algorithm.

###### detectionParser

Kind: Property

###### input

Kind: Property

Input message with data to be inferred upon

###### inputDepth

Kind: Property

Input message with depth data used to retrieve spatial information about
detected object Default queue is non-blocking with size 4

###### neuralNetwork

Kind: Property

###### out

Kind: Property

Outputs ImgDetections message that carries parsed detection results.

###### outNetwork

Kind: Property

Outputs unparsed inference results.

###### passthrough

Kind: Property

Passthrough message on which the inference was performed.

Suitable for when input queue is set to non-blocking behavior.

###### passthroughDepth

Kind: Property

Passthrough message for depth frame on which the spatial location calculation
was performed. Suitable for when input queue is set to non-blocking behavior.

###### spatialLocationCalculator

Kind: Property

##### depthai.node.SpatialLocationCalculator(depthai.DeviceNode)

Kind: Class

SpatialLocationCalculator node. Calculates the spatial locations of detected
objects based on the input depth map. Spatial location calculations can be
additionally refined by using a segmentation mask. If keypoints are provided,
the spatial location is calculated around each keypoint.

###### runOnHost(self) -> bool: bool

Kind: Method

Check if the node is set to run on host

###### setRunOnHost(self, runOnHost: bool)

Kind: Method

Specify whether to run on host or device By default, the node will run on
device.

###### initialConfig

Kind: Property

Initial config to use when calculating spatial location data.

###### inputConfig

Kind: Property

Input SpatialLocationCalculatorConfig message with ability to modify parameters
in runtime. Default queue is non-blocking with size 4.

###### inputDepth

Kind: Property

Input message with depth data used to retrieve spatial information about
detected object. Default queue is non-blocking with size 4.

###### inputDetections

Kind: Property

Input messages on which spatial location will be calculated. Possible datatypes
are ImgDetections or Keypoints.

###### out

Kind: Property

Outputs SpatialLocationCalculatorData message that carries spatial locations for
each additional ROI that is specified in the config.

###### outputDetections

Kind: Property

Outputs SpatialImgDetections message that carries spatial locations along with
original input data.

###### passthroughDepth

Kind: Property

Passthrough message on which the calculation was performed. Suitable for when
input queue is set to non-blocking behavior.

##### depthai.node.StereoDepth(depthai.DeviceNode)

Kind: Class

StereoDepth node. Compute stereo disparity and depth from left-right image pair.

###### depthai.node.StereoDepth.PresetMode

Kind: Class

Preset modes for stereo depth.

Members:

  FAST_ACCURACY

  FAST_DENSITY

  DEFAULT

  FACE

  HIGH_DETAIL

  ROBOTICS

  DENSITY

  ACCURACY

###### ACCURACY: typing.ClassVar[StereoDepth.PresetMode]

Kind: Class Variable

###### DEFAULT: typing.ClassVar[StereoDepth.PresetMode]

Kind: Class Variable

###### DENSITY: typing.ClassVar[StereoDepth.PresetMode]

Kind: Class Variable

###### FACE: typing.ClassVar[StereoDepth.PresetMode]

Kind: Class Variable

###### FAST_ACCURACY: typing.ClassVar[StereoDepth.PresetMode]

Kind: Class Variable

###### FAST_DENSITY: typing.ClassVar[StereoDepth.PresetMode]

Kind: Class Variable

###### HIGH_DETAIL: typing.ClassVar[StereoDepth.PresetMode]

Kind: Class Variable

###### ROBOTICS: typing.ClassVar[StereoDepth.PresetMode]

Kind: Class Variable

###### __members__: typing.ClassVar[dict[str, StereoDepth.PresetMode]]

Kind: Class Variable

###### __eq__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __getstate__(self) -> int: int

Kind: Method

###### __hash__(self) -> int: int

Kind: Method

###### __index__(self) -> int: int

Kind: Method

###### __init__(self, value: int)

Kind: Method

###### __int__(self) -> int: int

Kind: Method

###### __ne__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __repr__(self) -> str: str

Kind: Method

###### __setstate__(self, state: int)

Kind: Method

###### __str__(self) -> str: str

Kind: Method

###### name

Kind: Property

###### value

Kind: Property

###### __init__()

Kind: Method

###### build()

Kind: Method

###### enableDistortionCorrection(self, arg0: bool)

Kind: Method

Equivalent to useHomographyRectification(!enableDistortionCorrection)

###### loadMeshData()

Kind: Method

Specify mesh calibration data for 'left' and 'right' inputs, as vectors of
bytes. Overrides useHomographyRectification behavior. See `loadMeshFiles` for
the expected data format

###### loadMeshFiles(self, pathLeft: os.PathLike, pathRight: os.PathLike)

Kind: Method

Specify local filesystem paths to the mesh calibration files for 'left' and
'right' inputs.

When a mesh calibration is set, it overrides the camera intrinsics/extrinsics
matrices. Overrides useHomographyRectification behavior. Mesh format: a sequence
of (y,x) points as 'float' with coordinates from the input image to be mapped in
the output. The mesh can be subsampled, configured by `setMeshStep`.

With a 1280x800 resolution and the default (16,16) step, the required mesh size
is:

width: 1280 / 16 + 1 = 81

height: 800 / 16 + 1 = 51

###### setAlphaScaling(self, arg0: float)

Kind: Method

Free scaling parameter between 0 (when all the pixels in the undistorted image
are valid) and 1 (when all the source image pixels are retained in the
undistorted image). On some high distortion lenses, and/or due to rectification
(image rotated) invalid areas may appear even with alpha=0, in these cases alpha
< 0.0 helps removing invalid areas. See getOptimalNewCameraMatrix from opencv
for more details.

###### setBaseline(self, arg0: float)

Kind: Method

Override baseline from calibration. Used only in disparity to depth conversion.
Units are centimeters.

###### setDefaultProfilePreset(self, arg0: StereoDepth.PresetMode)

Kind: Method

Sets a default preset based on specified option.

Parameter ``mode``:
    Stereo depth preset mode

###### setDepthAlign()

Kind: Method

###### setDepthAlignmentUseSpecTranslation(self, arg0: bool)

Kind: Method

Use baseline information for depth alignment from specs (design data) or from
calibration. Default: true

###### setDisparityToDepthUseSpecTranslation(self, arg0: bool)

Kind: Method

Use baseline information for disparity to depth conversion from specs (design
data) or from calibration. Default: true

###### setExtendedDisparity(self, enable: bool)

Kind: Method

Disparity range increased from 0-95 to 0-190, combined from full resolution and
downscaled images.

Suitable for short range objects. Currently incompatible with sub-pixel
disparity

###### setFocalLength(self, arg0: float)

Kind: Method

Override focal length from calibration. Used only in disparity to depth
conversion. Units are pixels.

###### setInputResolution()

Kind: Method

###### setLeftRightCheck(self, enable: bool)

Kind: Method

Computes and combines disparities in both L-R and R-L directions, and combine
them.

For better occlusion handling, discarding invalid disparity values

###### setMeshStep(self, width: int, height: int)

Kind: Method

Set the distance between mesh points. Default: (16, 16)

###### setNumFramesPool(self, arg0: int)

Kind: Method

Specify number of frames in pool.

Parameter ``numFramesPool``:
    How many frames should the pool have

###### setOutputKeepAspectRatio(self, keep: bool)

Kind: Method

Specifies whether the frames resized by `setOutputSize` should preserve aspect
ratio, with potential cropping when enabled. Default `true`

###### setOutputSize(self, width: int, height: int)

Kind: Method

Specify disparity/depth output resolution size, implemented by scaling.

Currently only applicable when aligning to RGB camera

###### setPostProcessingHardwareResources(self, arg0: int, arg1: int)

Kind: Method

Specify allocated hardware resources for stereo depth. Suitable only to increase
post processing runtime.

Parameter ``numShaves``:
    Number of shaves.

Parameter ``numMemorySlices``:
    Number of memory slices.

###### setRectification(self, enable: bool)

Kind: Method

Rectify input images or not.

###### setRectificationUseSpecTranslation(self, arg0: bool)

Kind: Method

Obtain rectification matrices using spec translation (design data) or from
calibration in calculations. Should be used only for debugging. Default: false

###### setRectifyEdgeFillColor(self, color: int)

Kind: Method

Fill color for missing data at frame edges

Parameter ``color``:
    Grayscale 0..255, or -1 to replicate pixels

###### setRuntimeModeSwitch(self, arg0: bool)

Kind: Method

Enable runtime stereo mode switch, e.g. from standard to LR-check. Note: when
enabled resources allocated for worst case to enable switching to any mode.

###### setSubpixel(self, enable: bool)

Kind: Method

Computes disparity with sub-pixel interpolation (3 fractional bits by default).

Suitable for long range. Currently incompatible with extended disparity

###### setSubpixelFractionalBits(self, subpixelFractionalBits: int)

Kind: Method

Number of fractional bits for subpixel mode. Default value: 3. Valid values:
3,4,5. Defines the number of fractional disparities: 2^x. Median filter
postprocessing is supported only for 3 fractional bits.

###### useHomographyRectification(self, arg0: bool)

Kind: Method

Use 3x3 homography matrix for stereo rectification instead of sparse mesh
generated on device. Default behaviour is AUTO, for lenses with FOV over 85
degrees sparse mesh is used, otherwise 3x3 homography. If custom mesh data is
provided through loadMeshData or loadMeshFiles this option is ignored.

Parameter ``useHomographyRectification``:
    true: 3x3 homography matrix generated from calibration data is used for
    stereo rectification, can't correct lens distortion. false: sparse mesh is
    generated on-device from calibration data with mesh step specified with
    setMeshStep (Default: (16, 16)), can correct lens distortion. Implementation
    for generating the mesh is same as opencv's initUndistortRectifyMap
    function. Only the first 8 distortion coefficients are used from calibration
    data.

###### confidenceMap

Kind: Property

Outputs ImgFrame message that carries RAW8 confidence map. Lower values mean
lower confidence of the calculated disparity value. RGB alignment, left-right
check or any postprocessing (e.g., median filter) is not performed on confidence
map.

###### debugDispCostDump

Kind: Property

Outputs ImgFrame message that carries cost dump of disparity map. Useful for
debugging/fine tuning.

###### debugDispLrCheckIt1

Kind: Property

Outputs ImgFrame message that carries left-right check first iteration (before
combining with second iteration) disparity map. Useful for debugging/fine
tuning.

###### debugDispLrCheckIt2

Kind: Property

Outputs ImgFrame message that carries left-right check second iteration (before
combining with first iteration) disparity map. Useful for debugging/fine tuning.

###### debugExtDispLrCheckIt1

Kind: Property

Outputs ImgFrame message that carries extended left-right check first iteration
(downscaled frame, before combining with second iteration) disparity map. Useful
for debugging/fine tuning.

###### debugExtDispLrCheckIt2

Kind: Property

Outputs ImgFrame message that carries extended left-right check second iteration
(downscaled frame, before combining with first iteration) disparity map. Useful
for debugging/fine tuning.

###### depth

Kind: Property

Outputs ImgFrame message that carries RAW16 encoded (0..65535) depth data in
depth units (millimeter by default).

Non-determined / invalid depth values are set to 0

###### disparity

Kind: Property

Outputs ImgFrame message that carries RAW8 / RAW16 encoded disparity data: RAW8
encoded (0..95) for standard mode; RAW8 encoded (0..190) for extended disparity
mode; RAW16 encoded for subpixel disparity mode: - 0..760 for 3 fractional bits
(by default) - 0..1520 for 4 fractional bits - 0..3040 for 5 fractional bits

###### initialConfig

Kind: Property

Initial config to use for StereoDepth.

###### inputAlignTo

Kind: Property

Input align to message. Default queue is non-blocking with size 1.

###### inputConfig

Kind: Property

Input StereoDepthConfig message with ability to modify parameters in runtime.

###### left

Kind: Property

Input for left ImgFrame of left-right pair

###### outConfig

Kind: Property

Outputs StereoDepthConfig message that contains current stereo configuration.

###### rectifiedLeft

Kind: Property

Outputs ImgFrame message that carries RAW8 encoded (grayscale) rectified frame
data.

###### rectifiedRight

Kind: Property

Outputs ImgFrame message that carries RAW8 encoded (grayscale) rectified frame
data.

###### right

Kind: Property

Input for right ImgFrame of left-right pair

###### syncedLeft

Kind: Property

Passthrough ImgFrame message from 'left' Input.

###### syncedRight

Kind: Property

Passthrough ImgFrame message from 'right' Input.

##### depthai.node.Sync(depthai.DeviceNode)

Kind: Class

Sync node. Performs syncing between image frames

###### depthai.node.Sync.TimestampSource

Kind: Class

Members:

  DEFAULT

  DEVICE

  HOST

  SYSTEM

###### DEFAULT: typing.ClassVar[depthai.SyncProperties.TimestampSource]

Kind: Class Variable

###### DEVICE: typing.ClassVar[depthai.SyncProperties.TimestampSource]

Kind: Class Variable

###### HOST: typing.ClassVar[depthai.SyncProperties.TimestampSource]

Kind: Class Variable

###### SYSTEM: typing.ClassVar[depthai.SyncProperties.TimestampSource]

Kind: Class Variable

###### __members__: typing.ClassVar[dict[str, depthai.SyncProperties.TimestampSource]]

Kind: Class Variable

###### __eq__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __getstate__(self) -> int: int

Kind: Method

###### __hash__(self) -> int: int

Kind: Method

###### __index__(self: depthai.SyncProperties.TimestampSource) -> int: int

Kind: Method

###### __init__(self: depthai.SyncProperties.TimestampSource, value: int)

Kind: Method

###### __int__(self: depthai.SyncProperties.TimestampSource) -> int: int

Kind: Method

###### __ne__(self, other: typing.Any) -> bool: bool

Kind: Method

###### __repr__(self) -> str: str

Kind: Method

###### __setstate__(self: depthai.SyncProperties.TimestampSource, state: int)

Kind: Method

###### __str__(self) -> str: str

Kind: Method

###### name

Kind: Property

###### value

Kind: Property

###### getProcessor(self) -> depthai.ProcessorType: depthai.ProcessorType

Kind: Method

Get on which processor the node should run

Returns:
    Processor type - Leon CSS or Leon MSS

###### getSyncAttempts(self) -> int: int

Kind: Method

Gets the number of sync attempts

###### getSyncThreshold(self) -> datetime.timedelta: datetime.timedelta

Kind: Method

Gets the maximal interval between messages in the group in milliseconds

###### getTimestampSource(self) -> depthai.SyncProperties.TimestampSource: depthai.SyncProperties.TimestampSource

Kind: Method

Get the timestamp source

###### runOnHost(self) -> bool: bool

Kind: Method

Check if the node is set to run on host

###### setProcessor(self, processorType: depthai.ProcessorType)

Kind: Method

Specify on which processor the node should run. RVC2 only.

Parameter ``type``:
    Processor type - Leon CSS or Leon MSS

###### setRunOnHost(self, runOnHost: bool)

Kind: Method

Specify whether to run on host or device By default, the node will run on
device.

###### setSyncAttempts(self, maxDataSize: int)

Kind: Method

Set the number of attempts to get the specified max interval between messages in
the group

Parameter ``syncAttempts``:
    Number of attempts to get the specified max interval between messages in the
    group: - if syncAttempts = 0 then the node sends a message as soon at the
    group is filled - if syncAttempts > 0 then the node will make syncAttemts
    attempts to synchronize before sending out a message - if syncAttempts = -1
    (default) then the node will only send a message if successfully
    synchronized

###### setSyncThreshold(self, syncThreshold: datetime.timedelta)

Kind: Method

Set the maximal interval between messages in the group

Parameter ``syncThreshold``:
    Maximal interval between messages in the group

###### setTimestampSource(self, source: depthai.SyncProperties.TimestampSource)

Kind: Method

Specify the timestamp source

###### inputs

Kind: Property

A map of inputs

###### out

Kind: Property

##### depthai.node.SystemLogger(depthai.DeviceNode)

Kind: Class

SystemLogger node. Send system information periodically.

###### getRate(self) -> float: float

Kind: Method

Gets logging rate, at which messages will be sent out

###### setRate(self, hz: float)

Kind: Method

Specify logging rate, at which messages will be sent out

Parameter ``hz``:
    Sending rate in hertz (messages per second)

###### out

Kind: Property

Outputs SystemInformation[RVC4] message that carries various system information
like memory and CPU usage, temperatures, ... For series 2 devices output
SystemInformation message, for series 4 devices output SystemInformationRVC4
message

##### depthai.node.Thermal(depthai.DeviceNode)

Kind: Class

Thermal node.

###### build(self, boardSocket: depthai.CameraBoardSocket = ..., fps: float = 25.0) -> Thermal: Thermal

Kind: Method

Build with a specific board socket and fps.

###### getBoardSocket(self) -> depthai.CameraBoardSocket: depthai.CameraBoardSocket

Kind: Method

Retrieves which board socket to use

Returns:
    Board socket to use

###### color

Kind: Property

Outputs YUV422i grayscale thermal image.

###### initialConfig

Kind: Property

Initial config to use for thermal sensor.

###### inputConfig

Kind: Property

Input ThermalConfig message with ability to modify parameters in runtime.
Default queue is non-blocking with size 4.

###### temperature

Kind: Property

Outputs FP16 (degC) thermal image.

##### depthai.node.ThreadedHostNode(depthai.ThreadedNode)

Kind: Class

###### __init__(self)

Kind: Method

###### createInput(self, name: str = '', group: str = '', blocking: bool = True, queueSize: int = 3, types: list [ depthai.Node.DatatypeHierarchy ] = ..., waitForMessage: bool = False) -> depthai.Node.Input: depthai.Node.Input

Kind: Method

###### createOutput(self, name: str = '', group: str = '', possibleDatatypes: list [ depthai.Node.DatatypeHierarchy ] = ...) -> depthai.Node.Output: depthai.Node.Output

Kind: Method

###### createSubnode(self, class_, args, kwargs)

Kind: Method

###### onStart(self)

Kind: Method

###### onStop(self)

Kind: Method

###### run(self)

Kind: Method

##### depthai.node.ToF(depthai.DeviceNodeGroup)

Kind: Class

###### create(device: depthai.Device) -> ToF: ToF

Kind: Static Method

###### build()

Kind: Method

###### getInitialConfig(self) -> depthai.ToFConfig: depthai.ToFConfig

Kind: Method

###### setInitialConfig(self, arg0: depthai.ToFConfig)

Kind: Method

###### amplitude

Kind: Property

Amplitude output

###### confidence

Kind: Property

Confidence output

###### depth

Kind: Property

Filtered depth output

###### imageFiltersInputConfig

Kind: Property

Input config for image filters

###### imageFiltersNode

Kind: Property

Image filters node

###### intensity

Kind: Property

Intensity output

###### phase

Kind: Property

Phase output

###### raw

Kind: Property

Raw data coming from the sensor

###### rawDepth

Kind: Property

Raw depth output from ToF sensor. On RVC2 this is connected to the unfiltered
base depth output. On RVC4 this is an unconnected placeholder output.

###### tofBaseInputConfig

Kind: Property

Input config for ToF base node

###### tofBaseNode

Kind: Property

ToF base node

##### depthai.node.ToFBase(depthai.DeviceNode)

Kind: Class

ToFBase node. Performs feature tracking and reidentification using motion
estimation between 2 consecutive frames.

###### build(self, boardSocket: depthai.CameraBoardSocket = ..., profile: depthai.ToFConfig.Profile = ..., fps: float | None = None) -> ToFBase: ToFBase

Kind: Method

Build with a specific board socket

###### getBoardSocket(self) -> depthai.CameraBoardSocket: depthai.CameraBoardSocket

Kind: Method

Retrieves which board socket to use

Returns:
    Board socket to use

###### amplitude

Kind: Property

###### depth

Kind: Property

###### initialConfig

Kind: Property

Initial config to use for feature tracking.

###### inputConfig

Kind: Property

Input ToFConfig message with ability to modify parameters in runtime. Default
queue is non-blocking with size 4.

###### intensity

Kind: Property

###### phase

Kind: Property

###### raw

Kind: Property

##### depthai.node.ToFDepthConfidenceFilter(depthai.DeviceNode)

Kind: Class

Node for depth confidence filter, designed to be used with the `ToF` node.

###### build()

Kind: Method

###### runOnHost(self) -> bool: bool

Kind: Method

Check if the node is set to run on host

###### setRunOnHost(self, runOnHost: bool)

Kind: Method

Specify whether to run on host or device By default, the node will run on
device.

###### amplitude

Kind: Property

Amplitude frame image, expected ImgFrame type is RAW8 or RAW16.

###### confidence

Kind: Property

RAW16 encoded confidence frame

###### depth

Kind: Property

Depth frame image, expected ImgFrame type is RAW8 or RAW16.

###### filteredDepth

Kind: Property

RAW16 encoded filtered depth frame

###### initialConfig

Kind: Property

Initial config for ToF depth confidence filter.

###### inputConfig

Kind: Property

Config message for runtime filter configuration

##### depthai.node.UVC(depthai.DeviceNode)

Kind: Class

UVC (USB Video Class) node

###### setGpiosOnInit(self, list: dict [ int , int ])

Kind: Method

Set GPIO list <gpio_number, value> for GPIOs to set (on/off) at init

###### setGpiosOnStreamOff(self, list: dict [ int , int ])

Kind: Method

Set GPIO list <gpio_number, value> for GPIOs to set when streaming is disabled

###### setGpiosOnStreamOn(self, list: dict [ int , int ])

Kind: Method

Set GPIO list <gpio_number, value> for GPIOs to set when streaming is enabled

###### input

Kind: Property

Input for image frames to be streamed over UVC Default queue is blocking with
size 8

##### depthai.node.VideoEncoder(depthai.DeviceNode)

Kind: Class

VideoEncoder node. Encodes frames into MJPEG, H264 or H265.

###### __init__(self, input: depthai.Node.Output, bitrate: float = 0, frameRate: float = 30.0, profile: depthai.VideoEncoderProperties.Profile = ..., keyframeFrequency: int = 30, lossless: bool = False, quality: int = 80)

Kind: Method

###### build(self, input: depthai.Node.Output, bitrate: float = 0, frameRate: float = 30.0, profile: depthai.VideoEncoderProperties.Profile = ..., keyframeFrequency: int = 30, lossless: bool = False, quality: int = 80) -> VideoEncoder: VideoEncoder

Kind: Method

###### getBitrate(self) -> int: int

Kind: Method

Get bitrate in bps

###### getBitrateKbps(self) -> int: int

Kind: Method

Get bitrate in kbps

###### getFrameRate(self) -> float: float

Kind: Method

Get frame rate

###### getKeyframeFrequency(self) -> int: int

Kind: Method

Get keyframe frequency

###### getLossless(self) -> bool: bool

Kind: Method

Get lossless mode. Applies only when using [M]JPEG profile.

###### getMaxOutputFrameSize(self) -> int: int

Kind: Method

###### getNumBFrames(self) -> int: int

Kind: Method

Get number of B frames

###### getNumFramesPool(self) -> int: int

Kind: Method

Get number of frames in pool

Returns:
    Number of pool frames

###### getProfile(self) -> depthai.VideoEncoderProperties.Profile: depthai.VideoEncoderProperties.Profile

Kind: Method

Get profile

###### getQuality(self) -> int: int

Kind: Method

Get quality

###### getRateControlMode(self) -> depthai.VideoEncoderProperties.RateControlMode: depthai.VideoEncoderProperties.RateControlMode

Kind: Method

Get rate control mode

###### setBitrate(self, bitrate: int)

Kind: Method

Set output bitrate in bps, for CBR rate control mode. 0 for auto (based on frame
size and FPS)

###### setBitrateKbps(self, bitrateKbps: int)

Kind: Method

Set output bitrate in kbps, for CBR rate control mode. 0 for auto (based on
frame size and FPS)

###### setDefaultProfilePreset(self, fps: float, profile: depthai.VideoEncoderProperties.Profile)

Kind: Method

Sets a default preset based on specified frame rate and profile

Parameter ``fps``:
    Frame rate in frames per second

Parameter ``profile``:
    Encoding profile

###### setFrameRate(self, frameRate: float)

Kind: Method

Sets expected frame rate

Parameter ``frameRate``:
    Frame rate in frames per second

###### setKeyframeFrequency(self, freq: int)

Kind: Method

Set keyframe frequency. Every Nth frame a keyframe is inserted.

Applicable only to H264 and H265 profiles

Examples:

- 30 FPS video, keyframe frequency: 30. Every 1s a keyframe will be inserted

- 60 FPS video, keyframe frequency: 180. Every 3s a keyframe will be inserted

###### setLossless(self, arg0: bool)

Kind: Method

Set lossless mode. Applies only to [M]JPEG profile

Parameter ``lossless``:
    True to enable lossless jpeg encoding, false otherwise

###### setMaxOutputFrameSize(self, maxFrameSize: int)

Kind: Method

Specifies maximum output encoded frame size

###### setNumBFrames(self, numBFrames: int)

Kind: Method

Set number of B frames to be inserted

###### setNumFramesPool(self, frames: int)

Kind: Method

Set number of frames in pool

Parameter ``frames``:
    Number of pool frames

###### setProfile(self, profile: depthai.VideoEncoderProperties.Profile)

Kind: Method

Set encoding profile

###### setQuality(self, quality: int)

Kind: Method

Set quality

Parameter ``quality``:
    Value between 0-100%. Approximates quality

###### setRateControlMode(self, mode: depthai.VideoEncoderProperties.RateControlMode)

Kind: Method

Set rate control mode

###### bitstream

Kind: Property

Outputs ImgFrame message that carries BITSTREAM encoded (MJPEG, H264 or H265)
frame data. Mutually exclusive with out.

###### input

Kind: Property

Input for NV12 ImgFrame to be encoded

###### out

Kind: Property

Outputs EncodedFrame message that carries encoded (MJPEG, H264 or H265) frame
data. Mutually exclusive with bitstream.

##### depthai.node.Vpp(depthai.DeviceNode)

Kind: Class

Vpp node. Apply Virtual Projection Pattern algorithm to stereo images based on
disparity.

###### build(self, leftInput: depthai.Node.Output, rightInput: depthai.Node.Output, disparity: depthai.Node.Output, confidence: depthai.Node.Output) -> Vpp: Vpp

Kind: Method

###### confidence

Kind: Property

###### disparity

Kind: Property

###### initialConfig

Kind: Property

Initial config of the node.

###### initialConfig.setter(self, arg1: depthai.VppConfig)

Kind: Method

###### inputConfig

Kind: Property

###### left

Kind: Property

###### leftOut

Kind: Property

Output ImgFrame message that carries the processed left image with virtual
projection pattern applied.

###### right

Kind: Property

###### rightOut

Kind: Property

Output ImgFrame message that carries the processed right image with virtual
projection pattern applied.

###### syncedInputs

Kind: Property

"Synchronised Left Img, Right Img, Dispatiy and confidence input."

##### depthai.node.Warp(depthai.DeviceNode)

Kind: Class

Warp node. Capability to crop, resize, warp, ... incoming image frames

###### getHwIds(self) -> list [ int ]: list [ int ]

Kind: Method

Retrieve which hardware warp engines to use

###### getInterpolation(self) -> depthai.Interpolation: depthai.Interpolation

Kind: Method

Retrieve which interpolation method to use

###### setHwIds(self, arg0: list [ int ])

Kind: Method

Specify which hardware warp engines to use

Parameter ``ids``:
    Which warp engines to use (0, 1, 2)

###### setInterpolation(self, arg0: depthai.Interpolation)

Kind: Method

Specify which interpolation method to use

Parameter ``interpolation``:
    type of interpolation

###### setMaxOutputFrameSize(self, arg0: int)

Kind: Method

Specify maximum size of output image.

Parameter ``maxFrameSize``:
    Maximum frame size in bytes

###### setNumFramesPool(self, arg0: int)

Kind: Method

Specify number of frames in pool.

Parameter ``numFramesPool``:
    How many frames should the pool have

###### setOutputSize()

Kind: Method

###### setWarpMesh()

Kind: Method

###### inputImage

Kind: Property

Input image to be modified Default queue is blocking with size 8

###### out

Kind: Property

Outputs ImgFrame message that carries warped image.
