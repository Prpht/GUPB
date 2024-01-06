from gupb.model import characters



class Strategy:
    def prepare_actions(self, brain: 'Brain') -> characters.Action:
        raise NotImplementedError()
