#!/usr/bin/env python
# -*- coding: UTF-8 -*-

"""
List of routines to analyze rice heterosis datasets.
Starting from a list of .count files. The .count files are generated by HT-seq.
"""

import os.path as op
import sys
import logging

import numpy as np
from collections import defaultdict

from jcvi.formats.base import BaseFile
from jcvi.apps.base import OptionParser, ActionDispatcher, debug, glob, mkdir
debug()


class RiceSample (BaseFile):
    """
    Examples:
    1. LCS48-3_GTCCGC_L006_R_tophat_accepted_hits.count
    2. RF18-1_GTTTCG_L003_R_tophat_accepted_hits.count

    First letter is always tissue: L - leaf, R - root
    Next componet before dash is sample name:
    CS48 (9311)  is parent for F, CS66 (nipponbare) is parent for C
    Each family has a sequential id, in the second example, family ID is 18. Two
    parents for that family is F (CS48) and 18, hybrid progeny is F18.
    """
    def __init__(self, filename):
        super(RiceSample, self).__init__(filename)
        self.shortname = name = op.basename(filename).split("_")[0]
        name, rep = name.split("-")
        tissue, ind = name[0], name[1:]
        self.tissue, self.ind = tissue, ind
        self.rep = rep
        self.P1 = self.P2 = "na"
        if ind in ("CS48", "CS66"):
            self.label = "P1"
            self.family = "Recur"
        elif ind[0] in ("F", "C"):
            self.label = "F1"
            self.P1 = "CS48" if ind[0] == "F" else "CS66"
            self.P2 = ind[1:]
            self.family = int(ind[1:])
        else:
            self.label = "P2"
            self.family = int(ind)

        fp = open(filename)
        data = [row.split() for row in fp]
        self.header, self.data = zip(*data)
        self.data = np.array(self.data, dtype=np.int32)
        self.working = True


    def __str__(self):
        return "\t".join(str(x) for x in (self.filename, self.tissue,
                          self.label, self.family, self.rep))

    def merge(self, rs):
        logging.debug("Merge '{0}' and '{1}'".format(self.filename, rs.filename))
        self.filename = ",".join((self.filename, rs.filename))
        assert self.tissue == rs.tissue
        assert self.ind == rs.ind
        assert self.rep == rs.rep
        assert self.label == rs.label
        assert self.family == rs.family
        assert self.P1 == rs.P1
        assert self.P2 == rs.P2
        assert self.header == rs.header
        self.data += rs.data


def main():

    actions = (
        ('prepare', 'parse list of count files and group per family'),
            )
    p = ActionDispatcher(actions)
    p.dispatch(globals())


def merge_counts(ss, outfile):
    fw = open(outfile, "w")
    header = ["Gene"] + [x.shortname for x in ss]
    print >> fw, "\t".join(header)
    data = [ss[0].header] + [x.data for x in ss]
    data = zip(*data)
    for a in data:
        print >> fw, "\t".join(str(x) for x in a)
    logging.debug("File `{0}` written (size={1}).".format(outfile, len(ss)))


def prepare(args):
    """
    %prog prepare countfolder families

    Parse list of count files and group per family into families folder.
    """
    p = OptionParser(prepare.__doc__)
    opts, args = p.parse_args(args)

    if len(args) != 2:
        sys.exit(not p.print_help())

    counts, families = args
    countfiles = glob(op.join(counts, "*.count"))
    countsdb = defaultdict(list)
    for c in countfiles:
        rs = RiceSample(c)
        countsdb[(rs.tissue, rs.ind)].append(rs)

    # Merge duplicates - data sequenced in different batches
    key = lambda x: (x.label, x.rep)
    for (tissue, ind), rs in sorted(countsdb.items()):
        rs.sort(key=key)
        nrs = len(rs)
        for i in xrange(nrs):
            ri = rs[i]
            if not ri.working:
                continue
            for j in xrange(i + 1, nrs):
                rj = rs[j]
                if key(ri) != key(rj):
                    continue
                ri.merge(rj)
                rj.working = False
        countsdb[(tissue, ind)] = [x for x in rs if x.working]

    # Group into families
    mkdir("families")
    for (tissue, ind), r in sorted(countsdb.items()):
        r = list(r)
        if r[0].label != "F1":
            continue
        P1, P2 = r[0].P1, r[0].P2
        P1, P2 = countsdb[(tissue, P1)], countsdb[(tissue, P2)]
        rs = P1 + P2 + r
        groups = [1] * len(P1) + [2] * len(P2) + [3] * len(r)
        assert len(rs) == len(groups)

        outfile = "-".join((tissue, ind))
        merge_counts(rs, op.join(families, outfile))
        groupsfile = outfile + ".groups"
        fw = open(op.join(families, groupsfile), "w")
        print >> fw, ",".join(str(x) for x in groups)
        fw.close()


if __name__ == '__main__':
    main()
