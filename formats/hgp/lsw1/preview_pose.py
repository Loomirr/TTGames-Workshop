"""Reversible display-pose corrections for verified original LSW1 PC rigs.

These are not bind-pose repairs or automatic ANI ownership. Keep native data
unchanged and disable these offsets before applying a complete animation pose.
See docs/HAND_PREVIEW.md for original-file evidence and remaining limits.
"""
import hashlib
import struct


CLONE_SHORT_HAND_BIND = 'aa997da51c3f88c10654b833534106dbc6e6da0180015d2d60ff581c8e50c829'


def skeleton_fingerprint(bones):
    """Include names, hierarchy and every local/inverse-bind float, not count."""
    digest = hashlib.sha256()
    for bone in bones:
        digest.update(bone['name'].encode('utf-8') + b'\0')
        digest.update(struct.pack('<i32f', bone['parent'], *bone['local'], *bone['inverse']))
    return digest.hexdigest()


def translation_offsets(bones):
    """Return parent-space native translations for the known short-hand bind.

    The longer hand translations occur in Clone Idle/Walk and the original
    Sand Trooper bind. This fingerprint matches six original Clone-family rigs;
    changed/unknown rigs, including Sand, receive no automatic correction.
    """
    if skeleton_fingerprint(bones) != CLONE_SHORT_HAND_BIND:
        return {}
    targets = {'leftElbow|leftHand': .04633813351392746,
               'rightElbow|rightHand': -.04633814096450806}
    return {bone['index']: (targets[bone['name']] - bone['local'][12], 0., 0.)
            for bone in bones if bone['name'] in targets}
