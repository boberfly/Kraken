from kraken import plugins
from kraken.core.maths import Vec3
from kraken_components.generic.fkChain_component import FKChainComponentGuide, FKChainComponentRig

from kraken.core.profiler import Profiler
from kraken.helpers.utility_methods import logHierarchy


Profiler.getInstance().push("fkChain_build")

fkChainGuide = FKChainComponentGuide("fkChain")
fkChainGuide.loadData(
                        {
                         "name": "fkChain",
                         "location": "L",
                         "numJoints": 4,
                         "jointPositions": [
                                            Vec3(0.9811, 9.769, -1.237),
                                            Vec3(5.4488, 8.4418, -1.237),
                                            Vec3(4.0, 3.1516, -1.237),
                                            Vec3(6.841, 1.0, -1.237),
                                            Vec3(9.841, 0.0, -1.237)
                                           ]
                        })

# Save the hand guide data for persistence.
saveData = fkChainGuide.saveData()

fkChainGuideData = fkChainGuide.getRigBuildData()

chain = FKChainComponentRig()
chain.loadData(fkChainGuideData)

builder = plugins.getBuilder()
builder.buildComponent(chain)

Profiler.getInstance().pop()

if __name__ == "__main__":
    print Profiler.getInstance().generateReport()
else:
    for each in chain.getItems().values():
        # Only log hierarchy for Layer objects as Layers in this test are added to
        # the component since there is no rig object.
        if each.isTypeOf('Layer'):
            logHierarchy(each)