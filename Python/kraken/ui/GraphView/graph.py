
import copy

from PySide import QtGui, QtCore

from node import Node
from connection import Connection
# from main_panel import MainPanel
from selection_rect import SelectionRect
from kraken.core.maths import Vec2
from kraken.core.kraken_system import KrakenSystem
from kraken.core.configs.config import Config

from kraken.ui.undoredo.undo_redo_manager import UndoRedoManager
from graph_commands import ConstructComponentCommand, SelectionChangeCommand

class Graph(QtGui.QGraphicsWidget):

    __backgroundColor = QtGui.QColor(50, 50, 50)
    __gridPenS = QtGui.QPen(QtGui.QColor(44, 44, 44, 255), 0.5)
    __gridPenL = QtGui.QPen(QtGui.QColor(40, 40, 40, 255), 1.0)
    __gridPenA = QtGui.QPen(QtGui.QColor(30, 30, 30, 255), 2.0)

    def __init__(self, parent, rig):
        super(Graph, self).__init__()
        self.setObjectName('graphWidget')

        self.setSizePolicy(QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding))
        parentSize = parent.size()
        self.setMinimumSize(parentSize.width(), parentSize.height())

        self.__parent = parent
        self.__rig = rig
        self.__scene = QtGui.QGraphicsScene()
        self.__scene.addItem(self)

        self.__nodes = {}
        self.__connections = {}
        self.__selection = []

        self.__itemGroup = QtGui.QGraphicsWidget(self)
        self._manipulationMode = 0
        self._dragging = False
        self._selectionRect = None
        self._selectionchanged = False

        self.displayGraph()

        self.undoManager  = UndoRedoManager()

    def graphView(self):
        return self.__parent

    def scene(self):
        return self.__scene

    def itemGroup(self):
        return self.__itemGroup

    def getRig(self):
        return self.__rig

    #####################
    ## Nodes

    def addNode(self, component):
        node = Node(self, component)
        self.__nodes[node.getName()] = node
        return node

    def removeNode(self, node):
        component = node.getComponent()
        self.__rig.removeChild( component )
        node.destroy()
        del self.__nodes[node.getName()]

    def getNode(self, name):
        if name in self.__nodes:
            return self.__nodes[name]
        return None

    def getNodes(self):
        return self.__nodes

    def nodeNameChanged(self, origName, newName ):
        if newName in self.__nodes and self.__nodes[origName] != self.__nodes[newName]:
            raise Exception("New name collides with existing node.")
        node = self.__nodes[origName]
        self.__nodes[newName] = node
        del self.__nodes[origName]

    def clearSelection(self):
        for node in self.__selection:
            node.setSelected(False)
        self.__selection = []

    def selectNode(self, node, clearSelection=False):
        if clearSelection is True:
            self.clearSelection()

        if node in self.__selection:
            raise IndexError("Node is already in selection!")

        node.setSelected(True)

        self.__selection.append(node)

    def deselectNode(self, node):

        node.setSelected(False)

        if node not in self.__selection:
            raise IndexError("Node is not in selection!")

        self.__selection.remove(node)

    def getSelectedNodes(self):
        return self.__selection


    def deleteSelectedNodes(self):
        selectedNodes = self.getSelectedNodes()
        names = ""
        for node in selectedNodes:
            self.removeNode(node)


    def frameNodes(self, nodes):
        if len(nodes) == 0:
            return

        def computeWindowFrame():
            windowRect = self.mapRectToItem(self.itemGroup(), self.windowFrameGeometry())
            windowRect.setLeft(windowRect.left() + 16)
            windowRect.setRight(windowRect.right() - 16)
            windowRect.setTop(windowRect.top() + 16)
            windowRect.setBottom(windowRect.bottom() - 16)
            return windowRect

        nodesRect = None
        for node in nodes:
            nodeRect = self.mapToScene(node.transform().map(node.rect())).boundingRect()
            if nodesRect is None:
                nodesRect = nodeRect
            else:
                nodesRect = nodesRect.united(nodeRect)

        windowRect = computeWindowFrame()
        scaleX = windowRect.width() / nodesRect.width()
        scaleY = windowRect.height() / nodesRect.height()
        if scaleY > scaleX:
            scale = scaleX
        else:
            scale = scaleY

        transform = self.itemGroup().transform()
        transform.scale(scale, scale)
        if transform.m11() > 1.0 or transform.m22() > 1.0:
            transform.scale(1.0/transform.m11(), 1.0/transform.m22())
        self.itemGroup().setTransform(transform)

        # After zooming, recompute the window boundaries and compute the pan.
        windowRect = computeWindowFrame()
        pan = windowRect.center() - nodesRect.center()
        self.itemGroup().translate(pan.x(), pan.y())

        # Update the main panel when reframing.
        # self.__mainPanel.update()

    def frameSelectedNodes(self):
        self.frameNodes(self.getSelectedNodes())

    def frameAllNodes(self):
        allnodes = []
        for name, node in self.__nodes.iteritems():
            allnodes.append(node)
        self.frameNodes(allnodes)

    def getSelectedNodesPos(self):
        selectedNodes = self.getSelectedNodes()

        leftMostNode = None
        topMostNode = None
        for node in selectedNodes:
            nodePos = node.getGraphPos()

            if leftMostNode is None:
                leftMostNode = node
            else:
                if nodePos.x() < leftMostNode.getGraphPos().x():
                    leftMostNode = node

            if topMostNode is None:
                topMostNode = node
            else:
                if nodePos.y() < topMostNode.getGraphPos().y():
                    topMostNode = node

        xPos = leftMostNode.getGraphPos().x()
        yPos = topMostNode.getGraphPos().y()
        pos = QtCore.QPoint(xPos, yPos)

        return pos

    def __nodeCreated(self, event):
        graphPath = '.'.join(event['node']['path'].split('.')[0:-1])
        if graphPath == self.graphPath:
            self.addNode(event['node']['name'])

    def __nodeDestroyed(self, event):
        graphPath = '.'.join(event['node']['path'].split('.')[0:-1])
        if graphPath == self.graphPath:
            name = event['node']['path'].split('.')[-1]
            if name not in self.__nodes:
                raise Exception("Error removeing node:" + name+ ". Graph does not have a node of the given name.")
            node = self.__nodes[name]
            node.destroy()
            del self.__nodes[name]

    #######################
    ## Connections

    def addConnection(self, source, target):

        sourceComponent, outputName = tuple(source.split('.'))
        targetComponent, inputName = tuple(target.split('.'))
        sourceNode = self.getNode(sourceComponent)
        if not sourceNode:
            raise Exception("Component not found:" + sourceNode.getName())

        sourcePort = sourceNode.getOutPort(outputName)
        if not sourcePort:
            raise Exception("Component '" + sourceNode.getName() + "' does not have output:" + sourcePort.getName())


        targetNode = self.getNode(targetComponent)
        if not targetNode:
            raise Exception("Component not found:" + targetNode.getName())

        targetPort = targetNode.getInPort(inputName)
        if not targetPort:
            raise Exception("Component '" + targetNode.getName() + "' does not have input:" + targetPort.getName())

        connection = Connection(self, sourcePort, targetPort)
        sourcePort.addConnection(connection)
        targetPort.addConnection(connection)

        return connection

    #######################
    ## Graph
    def displayGraph(self):
        self.clear()

        guideComponents = self.__rig.getChildrenByType('Component')

        for component in guideComponents:
            self.addNode(component)

        for component in guideComponents:
            for i in range(component.getNumInputs()):
                componentInput = component.getInputByIndex(i)
                if componentInput.isConnected():
                    componentOutput = componentInput.getConnection()
                    self.addConnection(
                        source = componentOutput.getParent().getDecoratedName() + '.' + componentOutput.getName(),
                        target = component.getDecoratedName() + '.' + componentInput.getName()
                    )

        self.frameAllNodes()


    def clear(self):

        for connectionName, connection in self.__connections.iteritems():
            connection.destroy()
        for nodeName, node in self.__nodes.iteritems():
            node.destroy()

        self.__connections = {}
        self.__nodes = {}
        self.__selection = []

    #######################
    ## Copy/Paste

    def copySettings(self, pos):
        clipboardData = {}

        copiedComponents = []
        nodes = self.getSelectedNodes()
        for node in nodes:
            copiedComponents.append(node.getComponent())

        componentsJson = []
        connectionsJson = []
        for component in copiedComponents:
            componentsJson.append(component.copyData())

            for i in range(component.getNumInputs()):
                componentInput = component.getInputByIndex(i)
                if componentInput.isConnected():
                    componentOutput = componentInput.getConnection()
                    connectionJson = {
                        'source': componentOutput.getParent().getDecoratedName() + '.' + componentOutput.getName(),
                        'target': component.getDecoratedName() + '.' + componentInput.getName()
                    }

                    connectionsJson.append(connectionJson)

        clipboardData = {
            'components': componentsJson,
            'connections': connectionsJson,
            'copyPos': pos
        }

        return clipboardData

    def pasteSettings(self, clipboardData, pos, mirrored=False, createConnectionsToExistingNodes=True):

        krakenSystem = KrakenSystem.getInstance()
        delta = pos - clipboardData['copyPos']
        self.clearSelection()
        pastedComponents = {}
        nameMapping = {}

        for componentData in clipboardData['components']:
            componentClass = krakenSystem.getComponentClass(componentData['class'])
            component = componentClass(parent=self.__rig)
            decoratedName = componentData['name'] + component.getNameDecoration()
            nameMapping[decoratedName] = decoratedName
            if mirrored:
                config = Config.getInstance()
                mirrorMap = config.getNameTemplate()['mirrorMap']
                component.setLocation(mirrorMap[componentData['location']])
                nameMapping[decoratedName] = componentData['name'] + component.getNameDecoration()
                component.pasteData(componentData, setLocation=False)
            else:
                component.pasteData(componentData, setLocation=True)
            graphPos = component.getGraphPos( )
            component.setGraphPos(Vec2(graphPos.x + delta.x(), graphPos.y + delta.y()))
            node = self.addNode(component)
            self.selectNode(node, False)

            # save a dict of the nodes using the orignal names
            pastedComponents[nameMapping[decoratedName]] = component


        for connectionData in clipboardData['connections']:
            sourceComponentDecoratedName, outputName = connectionData['source'].split('.')
            targetComponentDecoratedName, inputName = connectionData['target'].split('.')

            sourceComponent = None

            # The connection is either between nodes that were pasted, or from pasted nodes
            # to unpasted nodes. We first check that the source component is in the pasted group
            # else use the node in the graph.
            if sourceComponentDecoratedName in nameMapping:
                sourceComponent = pastedComponents[nameMapping[sourceComponentDecoratedName]]
            else:
                if not createConnectionsToExistingNodes:
                    continue;

                # When we support copying/pasting between rigs, then we may not find the source
                # node in the target rig.
                if sourceComponentDecoratedName not in self.__nodes.keys():
                    continue
                node = self.__nodes[sourceComponentDecoratedName]
                sourceComponent = node.getComponent()

            targetComponentDecoratedName = nameMapping[targetComponentDecoratedName]
            targetComponent = pastedComponents[targetComponentDecoratedName]

            outputPort = sourceComponent.getOutputByName(outputName)
            inputPort = targetComponent.getInputByName(inputName)

            inputPort.setConnection(outputPort)
            self.addConnection(
                source = sourceComponent.getDecoratedName() + '.' + outputPort.getName(),
                target = targetComponent.getDecoratedName() + '.' + inputPort.getName()
            )


    #######################
    ## Events

    def mousePressEvent(self, event):
        if event.button() is QtCore.Qt.MouseButton.LeftButton:
            mouseDownPos = self.mapToItem(self.itemGroup(), event.pos())
            self._selectionRect = SelectionRect(self.__itemGroup, mouseDownPos)
            self._dragging = False
            self._manipulationMode = 1
            self._mouseDownSelection = copy.copy(self.getSelectedNodes())

        elif event.button() is QtCore.Qt.MouseButton.MiddleButton:
            self.setCursor(QtCore.Qt.OpenHandCursor)
            self._manipulationMode = 2
            self._lastPanPoint = event.pos()

        else:
            super(Graph, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._manipulationMode == 1:
            dragPoint = self.mapToItem(self.itemGroup(), event.pos())
            self._selectionRect.setDragPoint(dragPoint)
            self.clearSelection()
            for name, node in self.getNodes().iteritems():
                if not node.isSelected() and self._selectionRect.collidesWithItem(node):
                    self.selectNode(node)
                    self._selectionchanged = True
            self._dragging = True

        elif self._manipulationMode == 2:
            (xfo, invRes) = self.__itemGroup.transform().inverted()
            delta = xfo.map(event.pos()) - xfo.map(self._lastPanPoint)
            self._lastPanPoint = event.pos()
            self.__itemGroup.translate(delta.x(), delta.y())

            # Call udpate to redraw background
            self.update()
        else:
            super(Graph, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._manipulationMode == 1:
            self.scene().removeItem(self._selectionRect)
            if not self._dragging:
                self.clearSelection()
            self._selectionRect = None
            self._manipulationMode = 0

            selection = self.getSelectedNodes()

            deselectedNodes = []
            selectedNodes = []

            for node in self._mouseDownSelection:
                if node not in selection:
                    deselectedNodes.append(node)

            for node in selection:
                if node not in self._mouseDownSelection:
                    selectedNodes.append(node)

            command = SelectionChangeCommand(self, selectedNodes, deselectedNodes)
            UndoRedoManager.getInstance().addCommand(command, invokeRedoOnAdd=False)

        elif self._manipulationMode == 2:
            self.setCursor(QtCore.Qt.ArrowCursor)
            self._manipulationMode = 0

        else:
            super(Graph, self).mouseReleaseEvent(event)

    def wheelEvent(self, event):

        (xfo, invRes) = self.__itemGroup.transform().inverted()
        topLeft = xfo.map(self.rect().topLeft())
        bottomRight = xfo.map(self.rect().bottomRight())
        center = ( topLeft + bottomRight ) * 0.5

        zoomFactor = 1.0 + event.delta() * self.__mouseWheelZoomRate

        transform = self.__itemGroup.transform()

        # Limit zoom to 3x
        if transform.m22() * zoomFactor >= 2.0 or transform.m22() * zoomFactor <= 0.25:
            return

        transform.scale(zoomFactor, zoomFactor)

        if transform.m22() > 0.01: # To avoid negative scalling as it would flip the graph
            self.__itemGroup.setTransform(transform)

            (xfo, invRes) = transform.inverted()
            topLeft = xfo.map(self.rect().topLeft())
            bottomRight = xfo.map(self.rect().bottomRight())
            newcenter = ( topLeft + bottomRight ) * 0.5

            # Re-center the graph on the old position.
            self.__itemGroup.translate(newcenter.x() - center.x(), newcenter.y() - center.y())

        self.resize(self.size())

        # Call udpate to redraw background
        self.update()

    def closeEvent(self, event):
        return super(Graph, self).closeEvent(event)


    #######################
    ## Drawing


    def paint(self, painter, option, widget):
        # return super(Graph, self).paint(painter, option, widget)

        rect = self.__itemGroup.mapRectFromParent(self.windowFrameRect())

        oldTransform = painter.transform()
        painter.setTransform(self.__itemGroup.transform(), True)

        painter.fillRect(rect, self.__backgroundColor)

        gridSize = 30
        left = int(rect.left()) - (int(rect.left()) % gridSize)
        top = int(rect.top()) - (int(rect.top()) % gridSize)

        # Draw horizontal fine lines
        gridLines = []
        painter.setPen(self.__gridPenS)
        y = float(top)
        while y < float(rect.bottom()):
            gridLines.append(QtCore.QLineF( rect.left(), y, rect.right(), y ))
            y += gridSize
        painter.drawLines(gridLines)

        # Draw vertical fine lines
        gridLines = []
        painter.setPen(self.__gridPenS)
        x = float(left)
        while x < float(rect.right()):
            gridLines.append(QtCore.QLineF( x, rect.top(), x, rect.bottom()))
            x += gridSize
        painter.drawLines(gridLines)

        # Draw thick grid
        gridSize = 30 * 10
        left = int(rect.left()) - (int(rect.left()) % gridSize)
        top = int(rect.top()) - (int(rect.top()) % gridSize)

        # Draw vertical thick lines
        gridLines = []
        painter.setPen(self.__gridPenL)
        x = left
        while x < rect.right():
            gridLines.append(QtCore.QLineF( x, rect.top(), x, rect.bottom() ))
            x += gridSize
        painter.drawLines(gridLines)

        # Draw horizontal thick lines
        gridLines = []
        painter.setPen(self.__gridPenL)
        y = top
        while y < rect.bottom():
            gridLines.append(QtCore.QLineF( rect.left(), y, rect.right(), y ))
            y += gridSize
        painter.drawLines(gridLines)

        painter.setTransform(oldTransform)

        return super(Graph, self).paint(painter, option, widget)

