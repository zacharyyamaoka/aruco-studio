"""Old records pin the preset they were made with (the versioned-rule
guarantee). Cells rule 2 (0b134f4) set the inkjet built-ins' cell_step_mm
0.042333 -> 0, so an old Fusion node pointing at a built-in would re-round:
web_api.legacy_presets() gives the pre-rule-2 built-ins (ids "@1", no
size_step), literal copies of main 03594f9's presets(). Plan and svg over a
seeded set of requests with them answer what 03594f9 answered (sha256,
fit_rect / extrude dropped: fields added since), also after the size step
resolver (barrier 11): no size_step + cell_step_mm 0.042333 is the old dot
path; {of: "dots"} is not (25.4 / 600 != 0.042333)."""
from __future__ import annotations

import hashlib
import json
import random

from aruco_studio import web_api as W

SEED = 11
COUNTS = {"single": (1, 1), "grid": (3, 1), "charuco": (5, 4)}


def cases(presets):
    """12 requests per type and preset, seeded: random rects and angles,
    the label on or off (the generator the pins were taken with)."""
    rng = random.Random(SEED)
    out = []
    for pre in presets:
        for kind in ("single", "grid", "charuco"):
            for k in range(12):
                cols, rows = COUNTS[kind]
                marker = {"type": kind, "dictionary": "DICT_4X4_50", "first_id": 3, "auto": True, "marker_mm": 30,
                          "checker_mm": 0, "separation_mm": 0, "cols": cols, "rows": rows, "turn": 0, "flip": False,
                          "quiet_modules": 1, "corner_mark": "none"}
                label = {"on": rng.random() < 0.5, "text": "#{ids}", "height_mm": 0, "side": "below", "gap_mm": 2,
                         "offset_mm": [0, 0]}
                rect = {"cx": 0, "cy": 0, "w": rng.uniform(20, 160), "h": rng.uniform(20, 120),
                        "angle_deg": rng.choice([0, 0, 30, -15])}
                out.append((f"{pre['id']}|{kind}|{k}",
                            {"marker": marker, "label": label, "preset": pre, "reference_face": False, "rect": rect}))
    return out


def digests(presets):
    out = {}
    for name, req in cases(presets):
        for fn in ("plan", "svg"):
            res = getattr(W, fn)(req)
            if isinstance(res, dict):                  # fields added since 03594f9
                res = {key: v for key, v in res.items() if key not in ("fit_rect", "extrude")}
            out[f"{name}|{fn}"] = hashlib.sha256(json.dumps(res, sort_keys=True).encode()).hexdigest()
    return out


def test_the_legacy_presets_are_03594f9s_built_ins():
    got = W.legacy_presets()
    assert [p["id"] for p in got] == ["builtin:inkjet-letter-vinyl@1", "builtin:inkjet-a4-vinyl@1"]
    for p in got:
        assert "size_step" not in p
        assert (p["method"], p["cell_step_mm"], p["dpi"], p["min_cell_mm"], p["margin_mm"], p["thickness_mm"]) ==             ("inkjet", 0.042333, 600, 1.0, 10.0, 0.1)
    assert [p["page_mm"] for p in got] == [[215.9, 279.4], [210.0, 297.0]]
    # through the worker's entry, and never in the UI's list
    assert json.loads(W.call("legacy_presets", "{}"))["result"] == got
    assert not {p["id"] for p in W.presets()} & {p["id"] for p in got}
    # a copy each call: a shell editing one cannot change the next
    got[0]["cell_step_mm"] = 0.0
    assert W.legacy_presets()[0]["cell_step_mm"] == 0.042333


def test_plan_and_svg_answer_what_03594f9_answered():
    got = digests(W.legacy_presets())
    assert len(got) == len(PINS_03594F9) == 144
    assert got == PINS_03594F9


def test_whole_dots_are_not_the_legacy_path():
    """The ruler can fail: the same presets with size_step {of: "dots"} (25.4 /
    600, not 0.042333) answer differently."""
    dots = [dict(p, size_step={"of": "dots"}) for p in W.legacy_presets()]
    got = digests(dots)
    same = sum(got[k] == v for k, v in PINS_03594F9.items())
    assert same < len(PINS_03594F9) // 2, same


# sha256 of each case's plan / svg at main 03594f9 (a temporary detached
# worktree), the presets being legacy_presets()'s objects
PINS_03594F9 = {
    "builtin:inkjet-letter-vinyl@1|single|0|plan": "b04697d532cf2d7528f5fdd4f93529dd5cb5a926790c7c9ebb0ecdedf2bccd13",
    "builtin:inkjet-letter-vinyl@1|single|0|svg": "5f35a37864b5b7a7f40c5ddd0c1cf64ec26fc4e057f2ccfec2e9305a266ced98",
    "builtin:inkjet-letter-vinyl@1|single|1|plan": "a9cea693df307cfd3abea8816ad796e22f4afcfc7011baaab671e2dcfaabeeb2",
    "builtin:inkjet-letter-vinyl@1|single|1|svg": "672e9cbdd5a8261f85225dbb70ac94dfd1a180dcd2427f7bdcb5540513fed463",
    "builtin:inkjet-letter-vinyl@1|single|2|plan": "6a04a24ca3c0fa732afbc12d59cedc72800e6585099858339126e0bbac938c11",
    "builtin:inkjet-letter-vinyl@1|single|2|svg": "d184bdcf71c8488727c06d0e9cf5f944b2276d5410c2a8c8f40c45543c2371f4",
    "builtin:inkjet-letter-vinyl@1|single|3|plan": "7c8f320e58ef0b230605d35113a725b3dfc1ba0a24333014725c528944086cca",
    "builtin:inkjet-letter-vinyl@1|single|3|svg": "454202e6e6f256ee786368b94cccb1450636f9af5e2f6f56c9f731b42d0373ba",
    "builtin:inkjet-letter-vinyl@1|single|4|plan": "232e30ebfeb5acc45d17f807f960c10543cb796b88b50c0bbf4347cf3c4f1a7f",
    "builtin:inkjet-letter-vinyl@1|single|4|svg": "1ddd29faad14559b9d4bc1bbe805c688ccbdb146ac63108c6c425292e006a4cb",
    "builtin:inkjet-letter-vinyl@1|single|5|plan": "8f1b40f04169f57c0d0a8787687d2a8aca13662e8bbcb53ed7eec15bafe6b7a7",
    "builtin:inkjet-letter-vinyl@1|single|5|svg": "92684fea74069bb192a3a4e055ad5a052a95edf5eb8247379556b565d38bc3fb",
    "builtin:inkjet-letter-vinyl@1|single|6|plan": "2be8162aa9b8c9d186760d71415a6887a2cedee9a776880f3d4a7d6fb0c2ac46",
    "builtin:inkjet-letter-vinyl@1|single|6|svg": "3aa883b4cc22c6c27dcde4715cbc05ecdacc55d3cb002ed64b8c951e2227cbc6",
    "builtin:inkjet-letter-vinyl@1|single|7|plan": "d139538bbda26bc39d0983902170dae52e12cdb79c1aebb43e5ca707ed3967bc",
    "builtin:inkjet-letter-vinyl@1|single|7|svg": "fd99d2f210cbc468269e18c216e24966587af3eda000629a5a3ae8872e317256",
    "builtin:inkjet-letter-vinyl@1|single|8|plan": "328fddb4a6aea0c295fff40ddc0b2ded375751476bcc43f79ec46ed5c7cd4b68",
    "builtin:inkjet-letter-vinyl@1|single|8|svg": "29ec43033186fd9bfaf58e13ff973649b530db64ad71bd75be6192f56eb4443e",
    "builtin:inkjet-letter-vinyl@1|single|9|plan": "1a7ee80311fd08f874f78b64b31c77715273655ed7f36be7ea82a5e3f92148dc",
    "builtin:inkjet-letter-vinyl@1|single|9|svg": "6189562c9376223b8428e4586773e3fbe88e0d1284ceb164acb92feaea42ac79",
    "builtin:inkjet-letter-vinyl@1|single|10|plan": "6533be694c71e7a1d4630694f456bafdbd88099b6e5093e4310646d3660a6b80",
    "builtin:inkjet-letter-vinyl@1|single|10|svg": "e8a92720c532a4dac18623bba49d82c992d9da32926b0cee57b3e7b8731fcb7b",
    "builtin:inkjet-letter-vinyl@1|single|11|plan": "9d78a898da19603dd4302dc8cfa2d99706539b9ad2e89431f6634f0053db7d21",
    "builtin:inkjet-letter-vinyl@1|single|11|svg": "6df86467326248986de08c4024de66a6d6821e12ba99d61f94fdfd753030ed90",
    "builtin:inkjet-letter-vinyl@1|grid|0|plan": "aa34db5b24f6cb77255650ccf69deaa01d52a3b5c2f22c9f58e70e0745eebb22",
    "builtin:inkjet-letter-vinyl@1|grid|0|svg": "abbbc1f02471406e0618c35a7c87efa960db2bbf0025ce5787443c3b040b09ae",
    "builtin:inkjet-letter-vinyl@1|grid|1|plan": "04531019088d6ddc454a373ffc2a570354cb6b2d2b4e7e7d6c1c2307a74e6637",
    "builtin:inkjet-letter-vinyl@1|grid|1|svg": "07f34c5df9c6f760f3caa9549360062cb2e000fa9aa1beda475e8715133c3dac",
    "builtin:inkjet-letter-vinyl@1|grid|2|plan": "18e3324483e8fdda52b1bc0a0a1975db8caa2d604fe5a2e9d5ccf402db23d881",
    "builtin:inkjet-letter-vinyl@1|grid|2|svg": "88867a9de6669ba51b25941f39ec9b8f778416fd44d5086bfaea87085e600709",
    "builtin:inkjet-letter-vinyl@1|grid|3|plan": "6c1f1377db4df22fdf02c34f9a5853dfa96b6e0635525637ae46eadb23533cec",
    "builtin:inkjet-letter-vinyl@1|grid|3|svg": "1adf5c8c451cc8de0b7bf4936daf1d6a7a0734ee5d337dde4019ffd4c6a4e286",
    "builtin:inkjet-letter-vinyl@1|grid|4|plan": "3a94afe73def81a7c46c7f8f27747d7b2512346ada7f3232e28726b7ce75b95c",
    "builtin:inkjet-letter-vinyl@1|grid|4|svg": "4a257078c0b190fc9d095d7f5a3d9c911f7dfdf6c5b0b87aa9b67c3f7a260c70",
    "builtin:inkjet-letter-vinyl@1|grid|5|plan": "10b3c0c8298f2f09cb36cdc7c8cd08acd99146113a4caacce35d7a63fffd4a2b",
    "builtin:inkjet-letter-vinyl@1|grid|5|svg": "67b4eaf63108a9c4ed081423d3e3b926875fcb53f0682fe5c3775d226954864a",
    "builtin:inkjet-letter-vinyl@1|grid|6|plan": "3804144ceafc1ebf45ac4b79d5f3e7b7e7bb0ae6950e2153a0c5624b7f99c8e1",
    "builtin:inkjet-letter-vinyl@1|grid|6|svg": "e2f4d2746ca9456aaa8d7eff27ed82e6848fa014041c89d488b66e3ffaf99229",
    "builtin:inkjet-letter-vinyl@1|grid|7|plan": "5b7a465d54fe7eae770c585e2c70de9cbd0a557db8f3bd87c2027dbae66bf326",
    "builtin:inkjet-letter-vinyl@1|grid|7|svg": "82ae02d6a981f8d276349011d70acc8ae6a53bf4390051fbce7046b84aaf6757",
    "builtin:inkjet-letter-vinyl@1|grid|8|plan": "438976279f2ad757ca5e37372de2dab27273b1b9ab390790992e2b467849ff57",
    "builtin:inkjet-letter-vinyl@1|grid|8|svg": "041ef14509d0866cc653ba7998b50c95241648352454694c5e611c4121d08025",
    "builtin:inkjet-letter-vinyl@1|grid|9|plan": "19c24865b75f1a8040a6352980974606ec16e79e58cb4824b19d8f32875bc1f9",
    "builtin:inkjet-letter-vinyl@1|grid|9|svg": "9296129cb2412ee3b98bdd0ec67efb19d0a1365807700b303c305072d36e20a6",
    "builtin:inkjet-letter-vinyl@1|grid|10|plan": "c45987d81dfd2818376a4e71e090e35970662e20f76d64de57b6ad8d58819411",
    "builtin:inkjet-letter-vinyl@1|grid|10|svg": "b549152add7feebf45be1b55e77dfd16a7f5366183b4ef89da8d61b810b0b726",
    "builtin:inkjet-letter-vinyl@1|grid|11|plan": "789cbbcb36a7dc8d3d01610c9a1ab9fada80ade0fc932c2fcd6156c6ca80019f",
    "builtin:inkjet-letter-vinyl@1|grid|11|svg": "c83ead78694069caf39990d3b5dc7b0e88b9909093c049e3a3a385b934630037",
    "builtin:inkjet-letter-vinyl@1|charuco|0|plan": "bcafccc72c8c54db8e295a3f77592c0adb4aca572eae3af3144b431343834395",
    "builtin:inkjet-letter-vinyl@1|charuco|0|svg": "13edf0ce526bf8c5ad2d52417c729769239c8f1f6be5ea10c37a82d4016f8e5b",
    "builtin:inkjet-letter-vinyl@1|charuco|1|plan": "87c1f11a6fcaf9676add117423d1fd65cbb1be80dcec6709721bd2c0ea381dc5",
    "builtin:inkjet-letter-vinyl@1|charuco|1|svg": "75cf68b11217773a2c6fb199df98316e5fef072b51efbd71ba675d13224705b5",
    "builtin:inkjet-letter-vinyl@1|charuco|2|plan": "b177b8c9b2d40f1d0a9ccb18921962cbd7553a6db042953731d6776c2405e27c",
    "builtin:inkjet-letter-vinyl@1|charuco|2|svg": "2067e66ee7fff66389bdaecaed57b52836e27a48bd927190a50198c5e36ec221",
    "builtin:inkjet-letter-vinyl@1|charuco|3|plan": "d8675b8994fb38ea261bd7a07717f168fc64a5576c1539148ff064d0e2f84af8",
    "builtin:inkjet-letter-vinyl@1|charuco|3|svg": "163c333925ba525afd2a92ab08f1bf10f4e0994f3635505433d1bf16a6a4f9c7",
    "builtin:inkjet-letter-vinyl@1|charuco|4|plan": "ce88ab8613436e5535c16dc0f2f28aa6164545ce3efef3b40959c5f0bd07f784",
    "builtin:inkjet-letter-vinyl@1|charuco|4|svg": "07d78d2615b4698c79d49745989602f5ea176b9757c08e03af680618fcea8ac8",
    "builtin:inkjet-letter-vinyl@1|charuco|5|plan": "730a5fab41d519cddab7ce331d9e8c260762a89420b91b7b003c520ed7d0e0da",
    "builtin:inkjet-letter-vinyl@1|charuco|5|svg": "2f244ae6a17494ac6b806683e0b85a65ffdf9cfefa5de5c657edcb4de7c834e3",
    "builtin:inkjet-letter-vinyl@1|charuco|6|plan": "d06c5f8c9e0032845871cd8fab03cac3ce4abcd1be06912bc44e0fca0dd0c5c1",
    "builtin:inkjet-letter-vinyl@1|charuco|6|svg": "b75f0831c510595c283c1b945938f40a34567e061dc9bcfc70f481fcd054b664",
    "builtin:inkjet-letter-vinyl@1|charuco|7|plan": "f4968e91406aa838edddc6651d5700d501dc9458b625fa607bc1735884cbc5df",
    "builtin:inkjet-letter-vinyl@1|charuco|7|svg": "5f187149b1713983e9e5adcecbb8ff125a0b40b5226e0d8a36730f1454432288",
    "builtin:inkjet-letter-vinyl@1|charuco|8|plan": "fe52c8d2766444efd60c306f46e0fa1c55d31df877e6b5add37ca8c5c07d7e56",
    "builtin:inkjet-letter-vinyl@1|charuco|8|svg": "4f19ddb5f3bc75006f5e714e8d8b78dd205be0aa1441940173535849d0060e9c",
    "builtin:inkjet-letter-vinyl@1|charuco|9|plan": "4e5f84f687df07acaa1ae6e0b583d0cb1cb5e9287631b28f126e2099bc0c745d",
    "builtin:inkjet-letter-vinyl@1|charuco|9|svg": "43d701662b379ee6a12aa16e7b3e4f2012c9762a6516643277e50cb115db33e1",
    "builtin:inkjet-letter-vinyl@1|charuco|10|plan": "636849945e7e51e73eb79ee61b1230aad4d4cf308e06532cd56e2b25ecb565f3",
    "builtin:inkjet-letter-vinyl@1|charuco|10|svg": "c3b86e4e61c2981f84712b3c2f0f6d3942d4b4fc1a449da24770ada40d0a2116",
    "builtin:inkjet-letter-vinyl@1|charuco|11|plan": "7a671f20b959ac3cce44ce8b6144f95746a5b2791cdce36de46061f365545990",
    "builtin:inkjet-letter-vinyl@1|charuco|11|svg": "0a0c791d4864fb75f04a94355cafdef22e1adefa29cc69179d7240b8f7436cb9",
    "builtin:inkjet-a4-vinyl@1|single|0|plan": "c59683662a4cde44894fc22f8f9ba848f81b744e7f865a2da4a46cf7dd257531",
    "builtin:inkjet-a4-vinyl@1|single|0|svg": "295f5f16bb7f0ccedd9e2231194f2ffc8de1429f3e1ee424e1494e55ae22c74f",
    "builtin:inkjet-a4-vinyl@1|single|1|plan": "1f73f497b7e570d86a4b3fd5af94b2e104aa8eb47f6863de89ca70e802acbfa3",
    "builtin:inkjet-a4-vinyl@1|single|1|svg": "6f707d6f0836044d56ef8c2de16464f71f04562dd863e3b985ea9d9843dcb45d",
    "builtin:inkjet-a4-vinyl@1|single|2|plan": "29cd576a1f40b9d1b3ea5b4657bb59bb1011e3f4d46ff9f6ee8ef709292eee6f",
    "builtin:inkjet-a4-vinyl@1|single|2|svg": "903b852d1c3e766a316c677b57a33fc13fc17327b276e04ae7d455ef84437967",
    "builtin:inkjet-a4-vinyl@1|single|3|plan": "d99e010843b836a012feeb0f2f791c2e98bad21e7d38ad694c7e69107c77292a",
    "builtin:inkjet-a4-vinyl@1|single|3|svg": "df5bbf6d27e32860d1c3d4cbbd4cd500c0baeeec274b465fb15990c69b768117",
    "builtin:inkjet-a4-vinyl@1|single|4|plan": "4c54b17733b69087727f24f126592d2e152e0f46ecef2147fd9f6aca02b22018",
    "builtin:inkjet-a4-vinyl@1|single|4|svg": "76ad78dde49fb0570a08f0665f6a947e7fc0f5e58d7b3d0b39b8239bf952616b",
    "builtin:inkjet-a4-vinyl@1|single|5|plan": "8250c4886178a32c4ac3ed194c9e9fca08e61f3e667967ac5872b719d81a5cd6",
    "builtin:inkjet-a4-vinyl@1|single|5|svg": "db6e321cab3fdca13117cffc36dea63a4c9381116d944061a4c13e5cd880412f",
    "builtin:inkjet-a4-vinyl@1|single|6|plan": "97f0c0a96268670a169ae1d08700521c799eaa9f090484132e44d6393e08c068",
    "builtin:inkjet-a4-vinyl@1|single|6|svg": "518500904542a342055b23310b3057c1cd158ed787affd6f90963e3b479f0494",
    "builtin:inkjet-a4-vinyl@1|single|7|plan": "40282c2713d1d8cf66a25482dde24ef2a735df78d5085721e2f2f44295a25f64",
    "builtin:inkjet-a4-vinyl@1|single|7|svg": "384aa50861bcda49880ab3d29992b579c1f872a9146ed5dbe66faa3dfb47cb3f",
    "builtin:inkjet-a4-vinyl@1|single|8|plan": "d4ce146e44fb81409cca4dd966863e581360cf8a76e816b09b0f1b43009a9397",
    "builtin:inkjet-a4-vinyl@1|single|8|svg": "6c799e484b03a05cb30c3c903088d3a1ad6c4c507cdffb73425184a57e1a45db",
    "builtin:inkjet-a4-vinyl@1|single|9|plan": "1bade2d78cef254e88840bc1011b556aa5d1b4cf3b94214a29734c8d945175f6",
    "builtin:inkjet-a4-vinyl@1|single|9|svg": "0730946b75442c3b4d73c572ec2173a4273bff443263ee509426044963ad371c",
    "builtin:inkjet-a4-vinyl@1|single|10|plan": "335714096d3092431c7876480de9013242fd753c3e986d026e9a2f5236832546",
    "builtin:inkjet-a4-vinyl@1|single|10|svg": "b037512bffac9d3a651aa870278270d3412911bd30beff4fa93fb45b292a5550",
    "builtin:inkjet-a4-vinyl@1|single|11|plan": "cd640b0eeb8fe67723dc8c0ec3b65d1879cd378d7903766b02229bd82b9d7487",
    "builtin:inkjet-a4-vinyl@1|single|11|svg": "b1ba6fa2985836976da11a7af16a541a0f23ed7ec0fcf7f45334f266bd26cf1f",
    "builtin:inkjet-a4-vinyl@1|grid|0|plan": "4cd985a46d6adfe9ffbe6fba612af3a58819a542fd54ac43c6dda97fb0c76c81",
    "builtin:inkjet-a4-vinyl@1|grid|0|svg": "7f8472b0b23a3d1d6f504179ffbcb143026b7cabe349e01230c05da43ea3cbfc",
    "builtin:inkjet-a4-vinyl@1|grid|1|plan": "37bafc6d0a91abe1d9adc54f4b1dd7e3f8f013c24a3418db823a2cee2869fc80",
    "builtin:inkjet-a4-vinyl@1|grid|1|svg": "ca35465204d306d8901b9ce6142b9a98f61bec6d34bdd098ad0827a35157438f",
    "builtin:inkjet-a4-vinyl@1|grid|2|plan": "13f2d2585a2427b4ae5aa5802d3c835e942eb55c717b0eb57fff3741bf2f79b5",
    "builtin:inkjet-a4-vinyl@1|grid|2|svg": "71a146421f4b48d50cec5bc78ac1c2b8709a30548b1b8757c77fdc4d6ec4fe88",
    "builtin:inkjet-a4-vinyl@1|grid|3|plan": "f6c84096967a8d4e6fadca27e76358713948ac8e37982c426acb30075f84026d",
    "builtin:inkjet-a4-vinyl@1|grid|3|svg": "c509cee0bac2c6c8a0007c88b49b985925b7ba1b9e78dd52d65b58f39bfe7a2e",
    "builtin:inkjet-a4-vinyl@1|grid|4|plan": "1b34b7ef001ceffa568559d455d0843cf49f03be64467009f0c222d8edbd580e",
    "builtin:inkjet-a4-vinyl@1|grid|4|svg": "8af9c587050700a33b38f42abae89faf13fa799b69424ee4736f81886ff0d8d4",
    "builtin:inkjet-a4-vinyl@1|grid|5|plan": "ce304221e514a4e9d4304ce8bbdc7acacd8e19b974cb42f669aba7d4819b26a7",
    "builtin:inkjet-a4-vinyl@1|grid|5|svg": "54af1625c005b6e11ca1bd351a09f27132fa83acc62117126311da835057d108",
    "builtin:inkjet-a4-vinyl@1|grid|6|plan": "a189d74140ac7e7272c2ddff6ed94333170a95440dbaef6df6876ea856909f44",
    "builtin:inkjet-a4-vinyl@1|grid|6|svg": "51bdc305d397029cbb7e969360b787bfe2d60fcb009599efaf4f383963db287a",
    "builtin:inkjet-a4-vinyl@1|grid|7|plan": "8b21a18497ad5b8171550c29d654ea61f284c6357926f4a41c5623fe9a53a74a",
    "builtin:inkjet-a4-vinyl@1|grid|7|svg": "b147d7b22eea42df7255a4591eb8a39a1b64735dfc20c2c18c5dcc35407c22ae",
    "builtin:inkjet-a4-vinyl@1|grid|8|plan": "70a39011ed8f32fe0b9ec8a62f66328a68daf174f42b8191f2e1716f85886296",
    "builtin:inkjet-a4-vinyl@1|grid|8|svg": "2aa0be9fdd6c48dadb470eab2e24d9d68be25ad545f5d5b7f77df9c20ddb5cee",
    "builtin:inkjet-a4-vinyl@1|grid|9|plan": "4539800ef4c4b2df2453a1a8e9ee8afee8d6fc5d08fe6628c18992106a7596ae",
    "builtin:inkjet-a4-vinyl@1|grid|9|svg": "ec29dec6f48a8b8702171830bb28df505329587c4d4b35fe3d378e673da33333",
    "builtin:inkjet-a4-vinyl@1|grid|10|plan": "877ee7001f0a107284d12edd59f019c6ba82bcbc5329e494df7fc7ad5c58668d",
    "builtin:inkjet-a4-vinyl@1|grid|10|svg": "95455e500d95f9f1f4e30c9ea8f4d70faffc6a2f568f8c52a8e9d926ce1ba5c0",
    "builtin:inkjet-a4-vinyl@1|grid|11|plan": "d244f0c129384ee9a8d532ae38975760e6eab55aa4292bcfb6648008160c9a5b",
    "builtin:inkjet-a4-vinyl@1|grid|11|svg": "ef8ac0024adecc04c1abf2a61c6f64910189476c4ea69e4dcdf382bfa94a702a",
    "builtin:inkjet-a4-vinyl@1|charuco|0|plan": "022456441c0ee7dc4ff50d7711ad8e6cd901d7bdc61e24fd878450b0e711b761",
    "builtin:inkjet-a4-vinyl@1|charuco|0|svg": "d592e7704ea54cf7822a7642a275122e05b4f055437de6110a786c68c92a8016",
    "builtin:inkjet-a4-vinyl@1|charuco|1|plan": "2b3ec6053da5a1af3a2e8b937fd1e7e1c0a89a3bd4f5a82072ace92f10d27b89",
    "builtin:inkjet-a4-vinyl@1|charuco|1|svg": "6599b427496216f728d1193d44f0234c8a70774b58d3a365092a112a8c91bf4c",
    "builtin:inkjet-a4-vinyl@1|charuco|2|plan": "8761480ebb20fba78f892c1cfa4f276aed5620cff93407d375418cb15d3d68e7",
    "builtin:inkjet-a4-vinyl@1|charuco|2|svg": "f0682c641d2abc222862df7a0b718e63327d058060363b4bb1f3d63a15aee13b",
    "builtin:inkjet-a4-vinyl@1|charuco|3|plan": "ca118527a16ad1ae44fbf043965956a2591f676705fc7d0162e9ec781e4102d4",
    "builtin:inkjet-a4-vinyl@1|charuco|3|svg": "4afbef3ef3ef10129dd9d9ee1b6ae73304db54c36410a0d87e6aaa4b4942c38f",
    "builtin:inkjet-a4-vinyl@1|charuco|4|plan": "2dc1df89c1e4ca7b30e8cf652df191823093e630cdcdb63ddabdc0fe29b757f9",
    "builtin:inkjet-a4-vinyl@1|charuco|4|svg": "6bba8101df49b7e663bb38ec37eb771b5da5ccfda6b0f4bb577301884c39c0e4",
    "builtin:inkjet-a4-vinyl@1|charuco|5|plan": "d99ac0d4c9f94cbb193c6842777c84911a1ab4b65e6d0cf73ac04ff7d56231f1",
    "builtin:inkjet-a4-vinyl@1|charuco|5|svg": "b0e144402510ad43496d101477eee7af1c00870f2704c55434f6aca092983a40",
    "builtin:inkjet-a4-vinyl@1|charuco|6|plan": "976337c80b7dd9a0437c0f290a74806f019b526e30c14ec902ed6b8d4f1498e8",
    "builtin:inkjet-a4-vinyl@1|charuco|6|svg": "99374e39d45a579a53218ef39b305340ee14d22a5e3a3bcf3dc9a3b96c04e61b",
    "builtin:inkjet-a4-vinyl@1|charuco|7|plan": "8c7b444bff3b9790fcf244c18e94ed058e1c1b3b4ac8f986add682b7cd19f09f",
    "builtin:inkjet-a4-vinyl@1|charuco|7|svg": "3f4086f3b7040e86d3560137e3714e1b0438a3bc096dfaf21acc6644ca0f8036",
    "builtin:inkjet-a4-vinyl@1|charuco|8|plan": "83cf315f2ad47fb81741fd63d6667e9928c24161c62c3625d6e37a7f6cf7c571",
    "builtin:inkjet-a4-vinyl@1|charuco|8|svg": "17d4e6ef6480cd1b9f0a0c05f01bdd1b033b7158453f2632f812745c5e2f1094",
    "builtin:inkjet-a4-vinyl@1|charuco|9|plan": "1ac554c9946cf96f52e52d6094cf18c42550d073b0a867b49aef94c474086274",
    "builtin:inkjet-a4-vinyl@1|charuco|9|svg": "f6f7305866aaf9fb7c5a646ca6aa7102d27a987ae411d477e30c1119f941f257",
    "builtin:inkjet-a4-vinyl@1|charuco|10|plan": "b2d6b83149977a88f1cc848ea17a36cb549d1e2491ad506669daa56bc375363d",
    "builtin:inkjet-a4-vinyl@1|charuco|10|svg": "80545357bb870fa5130e8675995142b4a15860ab38dc72e88436648f77dc63a6",
    "builtin:inkjet-a4-vinyl@1|charuco|11|plan": "5b831e287e11636701ab6c79f639d8baaa2a54265b1d0e5dfb6474fbff472e9c",
    "builtin:inkjet-a4-vinyl@1|charuco|11|svg": "73e92b0aaface2e0be0e72cb4fc4cd5c40082bd79c0201f368d0c262a4e30ab0",
}
