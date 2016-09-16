import logging
from collections import namedtuple

import numpy as np

from pymchelper.shieldhit.detector.detector_type import SHDetType
from pymchelper.shieldhit.detector.estimator_type import SHGeoType

logger = logging.getLogger(__name__)


class SHBinaryReader:
    """
    Reads binary output files generated by SHIELDHIT12A code.
    """
    def __init__(self, filename):
        self.filename = filename

    def read_header(self, detector):
        logger.info("Reading header: " + self.filename)

        detector.tripdose = 0.0
        detector.tripntot = -1

        # effective read
        # first figure out if this is a VOXSCORE card
        header_dtype = np.dtype([('__fo1', '<i4'), ('geotyp', 'S10')])
        header = np.fromfile(self.filename, header_dtype, count=1)

        if 'VOXSCORE' in header['geotyp'][0].decode('ascii'):
            header_dtype = np.dtype([('__fo1', '<i4'),     # 0x00
                                     ('geotyp', 'S10'),    # 0x04
                                     ('__fo2', '<i4'),     # 0x0E
                                     ('__fo3', '<i4'),     # 0x12
                                     ('nstat', '<i4'),     # 0x16 : nstat
                                     ('__fo4', '<i4'),     # 0x1A
                                     ('__foo1', '<i4'),    # 0x1E
                                     ('tds', '<f4'),       # 0x22 : tripdose
                                     ('__foo2', '<i4'),    # 0x26
                                     ('__foo3', '<i4'),    # 0x2A
                                     ('tnt', '<i8'),       # 0x2E : tripntot
                                     ('__foo4', '<i4'),    # 0x36
                                     ('__fo5', '<i4'),     # 0x3A
                                     # DET has 8x float64
                                     ('det', ('<f8', 8)),  # 0x3E : DET
                                     ('__fo6', '<i4'),     # 0x7E
                                     ('__fo7', '<i4'),     # 0x82
                                     # IDET has 11x int32
                                     ('idet', '<i4', 11),  # 0x86 : IDET
                                     ('__fo8', '<i4'),     # 0xB2
                                     ('reclen', '<i4')])   # 0xB6
            # payload starts at 0xBA (186)
            detector.payload_offset = 186
        else:
            # first figure out the length.
            header_dtype = np.dtype([('__fo1', '<i4'),
                                     ('geotyp', 'S10'),
                                     ('__fo2', '<i4'),
                                     ('__fo3', '<i4'),
                                     ('nstat', '<i4'),
                                     ('__fo4', '<i4'),
                                     ('__fo5', '<i4'),
                                     # DET has 8x float64
                                     ('det', ('<f8', 8)),  # DET
                                     ('__fo6', '<i4'),
                                     ('__fo7', '<i4'),
                                     # IDET has 11x int32
                                     ('idet', '<i4', 11),  # IDET
                                     ('__fo8', '<i4'),
                                     ('reclen', '<i4')])
            # payload starts at 0x9E (158)
            detector.payload_offset = 158

        header = np.fromfile(self.filename, header_dtype, count=1)
        detector.rec_size = header['reclen'][0] // 8

        if 'VOXSCORE' in header['geotyp'][0].decode('ascii'):
            detector.tripdose = header['tds'][0]
            detector.tripntot = header['tnt'][0]

        # map 10-elements table to namedtuple, for easier access
        # here is description of IDET table, assuming fortran-style numbering
        # (arrays starting from 1)
        # IDET(1) : Number of bins in first dimension. x or r or zones
        # IDET(2) : Number of bins in snd dimension, y or theta
        # IDET(3) : Number of bins in thrd dimension, z
        # IDET(4) : Particle type requested for scoring
        # IDET(5) : Detector type (see INITDET)
        # IDET(6) : Z of particle to be scored
        # IDET(7) : A of particle to be scored (only integers here)
        # IDET(8) : Detector material parameter
        # IDET(9) : Number of energy/amu (or LET) differential bins,
        #            negative if log.
        # IDET(10): Type of differential scoring, either LET, E/amu
        #            or polar angle
        # IDET(11): Starting zone of scoring for zone scoring
        DetectorAttributes = namedtuple('DetectorAttributes',
                                        ['dim_1_bins', 'dim_2_bins',
                                         'dim_3_bins',
                                         'particle_type', 'det_type',
                                         'particle_z', 'particle_a',
                                         'det_material',
                                         'diff_bins_no', 'diff_scoring_type',
                                         'starting_zone'])
        det_attribs = DetectorAttributes(*header['idet'][0])

        detector.nx = det_attribs.dim_1_bins
        detector.ny = det_attribs.dim_2_bins
        detector.nz = det_attribs.dim_3_bins

        # DET(1-3): start positions for x y z or r theta z
        # DET(4-6): stop positions for x y z or r theta z
        # DET(7)  : start differential grid
        # DET(8)  : stop differential grid
        detector.det = header['det']
        detector.particle = det_attribs.particle_type

        try:
            detector.geotyp = SHGeoType[header['geotyp'][0].decode('ascii').strip().lower()]
        except Exception:
            detector.geotyp = SHGeoType.unknown
        detector.nstat = header['nstat'][0]

        if detector.geotyp not in (SHGeoType.zone, SHGeoType.dzone):
            shift = 0
            if 'VOXSCORE' in header['geotyp'][0].decode('ascii'):
                shift = 1  # TODO to be investigated
            detector.xmin = header['det'][0][0 + shift]
            detector.ymin = header['det'][0][1 + shift]
            detector.zmin = header['det'][0][2 + shift]

            detector.xmax = header['det'][0][3 + shift]
            detector.ymax = header['det'][0][4 + shift]
            detector.zmax = header['det'][0][5 + shift]
        else:
            # special case for zone scoring, x min and max will be zone numbers
            detector.xmin = det_attribs.starting_zone
            detector.xmax = detector.xmin + detector.nx - 1
            detector.ymin = 0.0
            detector.ymax = 0.0
            detector.zmin = 0.0
            detector.zmax = 0.0

        detector.dettyp = SHDetType(det_attribs.det_type)

        # set units : detector.units are [x,y,z,v,data,detector_title]
        detector.units = [""] * 6
        detector.units[0:4] = SHBinaryReader.get_estimator_units(detector.geotyp)
        detector.units[4:6] = SHBinaryReader.get_detector_unit(detector.dettyp,
                                                               detector.geotyp)
        detector.title = detector.units[5]

    @staticmethod
    def get_estimator_units(geotyp):
        """
        TODO
        :param geotyp:
        :return:
        """
        _geotyp_units = {
            SHGeoType.msh: ("cm", "cm", "cm", "(nil)"),
            SHGeoType.dmsh: ("cm", "cm", "cm", "#/MeV"),
            SHGeoType.cyl: ("cm", "cm", "radians", "(nil)"),
            SHGeoType.dcyl: ("cm", "cm", "radians", "#/MeV"),
            SHGeoType.zone: ("zone number", "(nil)", "(nil)", "(nil)"),
            SHGeoType.voxscore: ("cm", "cm", "cm", "(nil)"),
            SHGeoType.geomap: ("cm", "cm", "cm", "(nil)"),
            SHGeoType.plane: ("cm", "cm", "cm", "(nil)"),  # TODO fix me later
        }
        _default_units = ("(nil)", "(nil)", "(nil)", "(nil)")
        return _geotyp_units.get(geotyp, _default_units)

    @staticmethod
    def get_detector_unit(detector_type, geotyp):
        """
        TODO
        :param detector_type:
        :param geotyp:
        :return:
        """
        if geotyp == SHGeoType.zone:
            dose_units = (" MeV/primary", "Dose*volume")
            alanine_units = ("MeV/primary", "Alanine RE*Dose*volume")
        else:
            dose_units = (" MeV/g/primary", "Dose")
            alanine_units = ("MeV/g/primary", "Alanine RE*Dose")

        _detector_units = {
            SHDetType.unknown: ("(nil)", "None"),
            SHDetType.energy: ("MeV/primary", "Energy"),
            SHDetType.fluence: (" cm^-2/primary", "Fluence"),
            SHDetType.crossflu: (" cm^-2/primary", "Planar fluence"),
            SHDetType.letflu: (" MeV/cm", "LET fluence"),
            SHDetType.dose: dose_units,
            SHDetType.dlet: ("MeV/cm", "dose-averaged LET"),
            SHDetType.tlet: ("MeV/cm", "track-averaged LET"),
            SHDetType.avg_energy: ("MeV", "Average energy"),
            SHDetType.avg_beta: ("(dimensionless)", "Average beta"),
            SHDetType.material: ("(nil)", "Material number"),
            SHDetType.alanine: alanine_units,
            SHDetType.counter: ("/primary", "Particle counter"),
            SHDetType.pet: ("/primary", "PET isotopes"),
            SHDetType.dletg: ("MeV/cm", "dose-averaged LET"),
            SHDetType.tletg: ("MeV/cm", "track-averaged LET"),
            SHDetType.zone: ("(dimensionless)", "Zone#"),
            SHDetType.medium: ("(dimensionless)", "Medium#"),
            SHDetType.rho: ("g/cm^3", "Density"),
        }
        return _detector_units.get(detector_type, ("(nil)", "(nil)"))

    def read_payload(self, detector):
        logger.info("Reading data: " + self.filename)

        if detector.geotyp == SHGeoType.unknown or \
           detector.dettyp == SHDetType.unknown:
            detector.data = []
            return

        # next read the data:
        offset_str = "S" + str(detector.payload_offset)
        record_dtype = np.dtype([('trash', offset_str),
                                 ('bin2', '<f8', detector.rec_size)])
        record = np.fromfile(self.filename, record_dtype, count=-1)
        # BIN(*)  : a large array holding results. Accessed using pointers.
        detector.data = record['bin2'][:][0]
        if detector.dimension == 0:
            detector.data = np.asarray([detector.data])

        if detector.geotyp == SHGeoType.plane:
            detector.data = np.asarray([detector.data])

        # normalize result if we need that.
        if detector.dettyp not in (SHDetType.dlet, SHDetType.tlet,
                                   SHDetType.avg_energy, SHDetType.avg_beta,
                                   SHDetType.material):
            detector.data /= np.float64(detector.nstat)

        detector.counter = 1

    def read(self, detector):
        self.read_header(detector)
        self.read_payload(detector)


class SHTextReader:
    """
    Reads plain text files with data saved by binary-to-ascii converter.
    """
    def __init__(self, filename):
        self.filename = filename

    def read_header(self, detector):
        # TODO
        pass

    def read_payload(self, detector):
        # TODO
        pass

    def read(self, detector):
        self.read_header(detector)
        self.read_payload(detector)
