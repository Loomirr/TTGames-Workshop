"""Analytic checks for ordinary shader arithmetic, independent of Blender."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
from shader_reference import ordinary_pixel, check_material, specular_pixel, specular_uv, check_specular_material, bump_pixel, tangent_light_vectors, check_bump_material

DARK = (((0, 0, 1), (0, 0, 0)),) * 3


class TriangleTangents(unittest.TestCase):
    def test_last_triangle_wins_and_untouched_slots_stay_unknown(self):
        from shader_tangents import strip_tangents
        result=strip_tangents(((0,0,0),(1,0,0),(0,1,0),(0,1,1),(8,8,8)),
                             ((0,0),(1,0),(0,1),(1,1),(0,0)),(0,1,2,3))
        self.assertEqual(result[0],(1,0,0))
        self.assertEqual(result[1:4],[(0,0,1)]*3)
        self.assertIsNone(result[4])

    def test_strip_bounds_and_degenerate_skip(self):
        from shader_tangents import strip_tangents
        self.assertEqual(strip_tangents(((0,0,0),)*3,((0,0),)*3,(0,0,1)),[None]*3)
        with self.assertRaises(ValueError):strip_tangents(((0,0,0),)*3,((0,0),)*3,(0,1,3))

    def test_mirrored_uvs_reverse_tangent_without_normalizing(self):
        from shader_tangents import triangle_basis
        self.assertEqual(triangle_basis(((0,0,0),(2,0,0),(0,3,0)),((0,0),(-1,0),(0,1))),
                         ((-2,0,0),(0,3,0)))

    def test_collapsed_uvs_use_native_fallback(self):
        from shader_tangents import triangle_basis
        self.assertEqual(triangle_basis(((0,0,0),(2,0,0),(0,3,0)),((0,0),(1,0),(0,0))),
                         ((0,0,0),(0,3,0)))

    def test_nearly_singular_uvs_do_not_explode(self):
        from shader_tangents import triangle_basis
        tangent,_=triangle_basis(((0,0,0),(2,0,0),(0,3,0)),((0,0),(1,0),(0,1e-6)))
        self.assertEqual(tangent,(2e-6,0,0))

    def test_rejects_bad_triangle_data(self):
        from shader_tangents import triangle_basis
        for positions,uvs in ((((0,0,0),)*2,((0,0),)*3),
                              (((0,0,0),)*3,((0,0),)*4),
                              (((0,0,float('nan')),)*3,((0,0),)*3)):
            with self.assertRaises(ValueError):triangle_basis(positions,uvs)


class ShaderArithmetic(unittest.TestCase):
    def test_relative_skin_register_addressing(self):
        from check_pixel_programs import interpret
        program='vs_2_0\nfrc r0, v0\nadd r0, v0, -r0\nmova a0.xyz, r0\nmov oPos, c1[a0.y]'
        self.assertEqual(interpret(program,{'v0':(0.5,2.75,1.25,0),'c3':(1,2,3,4)},{},output='oPos'),(1,2,3,4))
        with self.assertRaises(ValueError):interpret('vs_2_0\nmov oPos, c1[a0.y]',{}, {},output='oPos')

    def test_shadow_receiver_preserves_textured_and_untextured_difference(self):
        from shader_reference import shadow_receiver_pixel
        args=((1,1,1,.4),1,1,(0,.5,1,0),(1,1,1,0))
        self.assertEqual(shadow_receiver_pixel(*args),(.75,.75,.75,.8))
        self.assertEqual(shadow_receiver_pixel(*args,texture=(.5,.5,.5,.5)),(.75,.875,1.,.4))

    def test_shadow_behind_projector_is_disabled(self):
        from shader_reference import shadow_receiver_pixel
        for w in (-1.,0.):
            self.assertEqual(shadow_receiver_pixel((2,1,.5,.8),w,1,(0,0,0,0),(1,1,1,1)),(2,1,.5,1))

    def test_native_lighting_to_pixel_keeps_direction_length(self):
        from shader_reference import native_lighting
        ambient,lights=native_lighting((.5,1.,2.,99.),
            ((0,0,2),(0,0,0),(0,0,-3)),((1.,2.,4.,7.),(8.,8.,8.,8.),(3.,3.,3.,3.)))
        self.assertEqual(ordinary_pixel((1,1,1),.5,(0,0,.25),ambient,lights),(.5,1.,2.,1.))

    def test_native_lighting_rejects_bad_counts_and_nonfinite_values(self):
        from shader_reference import native_lighting
        good=[(0,0,0,1),((0,0,1),)*3,((1,1,1,1),)*3]
        for index,bad in ((0,(0,0,0)),(0,(0,0,0,float('nan'))),
                          (1,((0,0,1),)*2),(1,((0,0,float('inf')),)*3),
                          (2,((1,1,1),)*3),(2,((1,1,1,1),)*4)):
            values=good.copy();values[index]=bad
            with self.subTest(index=index,bad=bad),self.assertRaises(ValueError):
                native_lighting(*values)

    def test_texture_rgb_has_no_uncompensated_double_brightness(self):
        color = ordinary_pixel((.5, .25, 1), .2, (0, 0, 1), (1, 1, 1), DARK, (.8, .4, .2, .25))
        self.assertEqual(color, (.4, .1, .2, .1))

    def test_normal_length_and_direction_length_are_not_discarded(self):
        lights = (((0, 0, 2), (.5, .25, 1)), ((0, 0, -1), (10, 10, 10)), ((1, 0, 0), (10, 10, 10)))
        self.assertEqual(ordinary_pixel((1, 1, 1), .5, (0, 0, .25), (0, 0, 0), lights),
                         (.25, .125, .5, 1))

    def test_only_textured_rgb_is_saturated(self):
        self.assertEqual(ordinary_pixel((1, 1, 1), 1, (0, 0, 1), (2, -.5, .25), DARK), (2, -.5, .25, 1))
        self.assertEqual(ordinary_pixel((1, 1, 1), 1, (0, 0, 1), (2, -.5, .25), DARK, (1, 1, 1, 1)), (1, 0, .25, 1))

    def test_texture_alpha_is_multiplied_before_saturation(self):
        # clamp(2*a)*t would incorrectly give .5 here instead of .8.
        self.assertAlmostEqual(ordinary_pixel((1, 1, 1), .8, (0, 0, 1), (1, 1, 1), DARK, (1, 1, 1, .5))[3], .8)
        self.assertEqual(ordinary_pixel((1, 1, 1), 0, (0, 0, 1), (1, 1, 1), DARK)[3], 0)

    def test_invalid_inputs(self):
        args = [(1, 1, 1), .5, (0, 0, 1), (1, 1, 1), DARK]
        for index, bad in ((0, (1, 1)), (1, -1), (1, float('nan')), (2, (0, 0, float('inf'))), (4, DARK[:2])):
            with self.subTest(index=index, bad=bad):
                changed = args.copy(); changed[index] = bad
                with self.assertRaises(ValueError):
                    ordinary_pixel(*changed)

    def test_opaque_mode_10_accepts_cached_alpha_flags(self):
        check_material(dict(effect=0,attributes=0x3ed0201a,linked_material=0,normal_texture=None))

    def test_special_material_paths_are_refused(self):
        source = dict(effect=0, attributes=1, linked_material=0, normal_texture=None)
        check_material(source)
        for change in (dict(effect=129), dict(linked_material=1), dict(normal_texture=0), dict(attributes=2 << 16), dict(attributes=7)):
            with self.assertRaises(ValueError):
                check_material(dict(source, **change))


class SpecularArithmetic(unittest.TestCase):
    def test_legacy_plastic_is_explicit_and_keeps_other_guards(self):
        from shader_reference import check_legacy_plastic
        source = dict(effect=145, attributes=0, linked_material=0, normal_texture=None)
        check_legacy_plastic(source)
        with self.assertRaises(ValueError):
            check_material(source)
        for change in (dict(effect=135), dict(linked_material=2), dict(normal_texture=1),
                       dict(attributes=7), dict(attributes=2 << 16)):
            with self.assertRaises(ValueError):
                check_legacy_plastic(dict(source, **change))

    def test_highlight_is_separately_saturated_without_clamping_final_color(self):
        result = specular_pixel((1, 1, 1), .2, (0, 0, 1), (1, 1, 1), DARK,
                                (.75, .25, 0, 0), 2, (1, 1, 1, .5))
        self.assertEqual(result, (2, 2, 1, .2))

    def test_lookup_alpha_does_not_change_opacity(self):
        args = ((.2, .3, .4), .4, (0, 0, 1), (1, 1, 1), DARK)
        self.assertEqual(specular_pixel(*args, (1, .5, .25, 0), .1),
                         specular_pixel(*args, (1, .5, .25, 1), .1))
        with self.assertRaises(ValueError):
            specular_pixel(*args, (1, 1, 1, 1), float('nan'))

    def test_uv_uses_four_component_length_and_ignores_translation(self):
        rows = ((1, 0, 0, 999), (0, 1, 0, 999), (0, 0, 1, 999), (0, 0, 1, 999))
        u, v = specular_uv((1, 0, 1), rows)
        self.assertAlmostEqual(u, .5 + .5 / 3**.5)
        self.assertEqual(v, .5)
        for normal, matrix in (((0, 0, 0), rows), ((1, 0, 0), rows[:3]),
                               ((float('inf'), 0, 0), rows)):
            with self.assertRaises(ValueError):
                specular_uv(normal, matrix)

    def test_specular_gate_requires_verified_auxiliary(self):
        source = dict(effect=129, attributes=0, linked_material=2, normal_texture=None)
        auxiliary = dict(effect=129, attributes=0x3f514512, texture=0, diffuse=(1, 8, 9), linked_material=0)
        self.assertEqual(check_specular_material(source, auxiliary), .1)
        for change in (dict(effect=135), dict(texture=None), dict(linked_material=3),
                       dict(attributes=0x3f524512), dict(diffuse=(float('nan'), 1, 1))):
            with self.assertRaises(ValueError):
                check_specular_material(source, dict(auxiliary, **change))
        for change in (dict(effect=0), dict(linked_material=0), dict(normal_texture=1), dict(attributes=7)):
            with self.assertRaises(ValueError):
                check_specular_material(dict(source, **change), auxiliary)


class BumpArithmetic(unittest.TestCase):
    def test_texture_clamp_is_before_lighting_and_output_is_not_saturated(self):
        result = bump_pixel((1,1,1),.8,(.5,.5,1,0),(3,2,4),DARK,(1,1,1,.9))
        self.assertEqual(result[:3],(3,2,4))
        self.assertAlmostEqual(result[3],1.44)

    def test_bump_length_and_interpolated_light_length_are_preserved(self):
        lights = (((0,0,.25),(1,1,1)),) + DARK[1:]
        self.assertEqual(bump_pixel((1,1,1),1,(.5,.5,.75,1),(0,0,0),lights),(.125,.125,.125,1))
        self.assertEqual(bump_pixel((1,1,1),1,(.5,.5,.5,1),(0,0,0),lights),(0,0,0,1))

    def test_vertex_basis_projection_is_normalized_before_interpolation(self):
        projected = tangent_light_vectors((2,0,0),(0,-1,0),(0,0,3),(((1,1,0),(1,1,1)),)*3)
        self.assertAlmostEqual(projected[0][0],2/5**.5)
        self.assertAlmostEqual(projected[0][1],-1/5**.5)
        for bad in ((0,0,0),(float('nan'),0,0)):
            with self.assertRaises(ValueError):
                tangent_light_vectors(bad,(0,1,0),(0,0,1),(((1,0,0),(1,1,1)),)*3)

    def test_bump_gate_and_nonfinite_input_refusals(self):
        source = dict(effect=135,attributes=1,linked_material=2,normal_texture=3)
        auxiliary = dict(effect=135,attributes=0x3f520002,texture_aux=0x7fef,texture=3,linked_material=0)
        check_bump_material(source,auxiliary)
        for change in (dict(effect=145),dict(texture=4),dict(texture=None),dict(texture_aux=0x7ffe),dict(linked_material=3),dict(attributes=0x3f510002)):
            with self.assertRaises(ValueError):
                check_bump_material(source,dict(auxiliary,**change))
        for change in (dict(effect=145),dict(linked_material=0),dict(attributes=7),dict(attributes=2<<16)):
            with self.assertRaises(ValueError):
                check_bump_material(dict(source,**change),auxiliary)
        with self.assertRaises(ValueError):
            bump_pixel((1,1,1),.5,(.5,.5,float('nan'),1),(0,0,0),DARK)


class ReflectionArithmetic(unittest.TestCase):
    def test_edge_transition_and_direction(self):
        from shader_reference import reflection_terms
        direction,front=reflection_terms((0,0,2),(0,0,4),(0,0,3),(.05,.8,.2,.8))
        self.assertEqual(direction,(0,0,1));self.assertEqual(front,.05)
        self.assertAlmostEqual(reflection_terms((0,0,1),(0,0,1),(1,0,0),(.05,.8,.2,.8))[1],.8)
        self.assertAlmostEqual(reflection_terms((0,0,1),(0,0,1),(3**.5,0,1),(.05,.8,.2,.8))[1],.425)

    def test_textured_and_untextured_reflection_gain(self):
        from shader_reference import reflection_pixel
        args=((0,0,0),.8,(0,0,1),(1,1,1),DARK,(0,0,1),(0,0,1),(.5,.5,.2,.8),(.2,.4,.6,0))
        self.assertEqual(reflection_pixel(*args),(.1,.2,.3,1))
        self.assertEqual(reflection_pixel(*args,(1,1,1,.25)),(.2,.4,.6,.4))

    def test_skin_output_has_no_rigid_clamp(self):
        from shader_reference import reflection_pixel
        args=((1,1,1),.8,(0,0,1),(3,3,3),DARK,(0,0,1),(0,0,1),(.5,.5,.2,.8),(1,1,1,0))
        self.assertEqual(reflection_pixel(*args,(1,1,1,1)),(1,1,1,1))
        self.assertEqual(reflection_pixel(*args,(1,1,1,1),skinned=True),(6,6,6,1.6))
        self.assertEqual(reflection_pixel(*args,skinned=True),(4.5,4.5,4.5,1.6))

    def test_bump_reflection_adds_after_light_and_never_clamps(self):
        from shader_reference import bump_reflection_pixel
        args=((1,1,1),.8,(0,0,1),(0,0,0),DARK,(0,0,1),(0,0,1),(.5,.5,.2,.8),(2,4,6,0),(.5,.5,1,0))
        self.assertEqual(bump_reflection_pixel(*args),(1,2,3,1.6))
        self.assertEqual(bump_reflection_pixel(*args,(1,1,1,.5)),(2,4,6,.8))

    def test_invalid_vectors_and_parameters(self):
        from shader_reference import reflection_terms
        good=[(0,0,1),(0,0,1),(0,0,1),(.05,.8,.2,.8)]
        for i,bad in ((0,(0,0,0)),(1,(0,0,0)),(2,(0,0,float('inf'))),
                      (3,(.05,.8,.2,.2)),(3,(.05,float('nan'),.2,.8))):
            args=good.copy();args[i]=bad
            with self.assertRaises(ValueError):reflection_terms(*args)


if __name__ == '__main__':
    unittest.main()
