"""Render measured or simulated joint angles on the MuJoCo CAD model."""
import math

WIDTH = 352
HEIGHT = 320


class PoseRenderer:
    def __init__(self):
        import mujoco

        from .env import FurutaEnv

        self.mujoco = mujoco
        self.env = FurutaEnv()
        self.camera = mujoco.MjvCamera()
        self.camera.lookat[:] = [0, 0, -.055]
        self.camera.distance = .56
        self.camera.azimuth = 135
        self.camera.elevation = -22
        for name, color in (
            ('bending_pipe_geom', [.02, .66, .58, 1]),
            ('arm_holder_geom', [.92, .39, .17, 1]),
        ):
            geom = mujoco.mj_name2id(self.env.model, mujoco.mjtObj.mjOBJ_GEOM, name)
            if geom >= 0:
                self.env.model.geom_rgba[geom] = color
        self.env.renderer = mujoco.Renderer(self.env.model, height=HEIGHT, width=WIDTH)

    def image_data(self, row):
        env = self.env
        env.data.qpos[env.qids] = [
            math.radians(row['arm_deg']),
            env.up + math.radians(row['pendulum_deg']),
        ]
        self.mujoco.mj_forward(env.model, env.data)
        env.renderer.update_scene(env.data, camera=self.camera)
        rgb = env.renderer.render()
        return f'P6\n{WIDTH} {HEIGHT}\n255\n'.encode('ascii') + rgb.tobytes()

    def close(self):
        self.env.close()
